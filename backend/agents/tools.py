import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import Document
from agents.rag_agent import delete_document_chunks

def get_tools_schema() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_document_statistics",
                "description": "Obtenir le nombre de documents de l'utilisateur, filtrable par matière (subject).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "Le nom de la matière (ex: Mathématiques, Informatique). Laisser vide pour avoir le total."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_recent_documents",
                "description": "Lister les noms des documents de l'utilisateur, filtrable par matière.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "La matière pour filtrer. Laisser vide pour tous les documents."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Le nombre maximum de documents à retourner (par défaut 5, max 20)."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_document_by_name",
                "description": "Supprime un document de la base de données en utilisant son nom (original_name).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Le nom exact du fichier à supprimer."
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_documents_by_subject",
                "description": "Supprime tous les documents d'une matière spécifique (ou 'Non classé').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "La matière des documents à supprimer (ex: 'Non classé', 'Mathématiques'). Laisser vide pour supprimer les documents sans matière."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_report",
                "description": "Génère un rapport textuel structuré au format DOCX, le sauvegarde sur le serveur, et retourne une URL de téléchargement sécurisée.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Le titre principal du rapport."
                        },
                        "content": {
                            "type": "string",
                            "description": "Le contenu structuré du rapport (qui sera inséré dans le document Word)."
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_subjects",
                "description": "Créer une ou plusieurs nouvelles matières (subjects) dans le profil de l'utilisateur.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subjects": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des noms de matières à créer."
                        }
                    },
                    "required": ["subjects"]
                }
            }
        }
    ]

async def execute_tool(tool_name: str, args: Dict[str, Any], user_id: int, db: AsyncSession) -> str:
    try:
        if tool_name == "create_subjects":
            subjects = args.get("subjects", [])
            if not subjects:
                return json.dumps({"error": "Aucune matière fournie."})
            
            from core.database import UserSubject
            added = []
            existed = []
            for name in subjects:
                query = select(UserSubject).where(UserSubject.user_id == user_id, UserSubject.name == name)
                res = await db.execute(query)
                if not res.scalar_one_or_none():
                    new_subject = UserSubject(user_id=user_id, name=name)
                    db.add(new_subject)
                    added.append(name)
                else:
                    existed.append(name)
            
            await db.commit()
            return json.dumps({
                "result": f"Matières ajoutées avec succès : {', '.join(added)}." + (f" (Déjà existantes : {', '.join(existed)})" if existed else "")
            })

        elif tool_name == "get_document_statistics":
            subject = args.get("subject")
            query = select(func.count(Document.id)).where(Document.user_id == user_id)
            if subject:
                query = query.where(Document.subject.ilike(f"%{subject}%"))
            res = await db.execute(query)
            count = res.scalar()
            if subject:
                return json.dumps({"result": f"Il y a {count} document(s) dans la matière '{subject}'."})
            return json.dumps({"result": f"Il y a un total de {count} document(s)."})

        elif tool_name == "list_recent_documents":
            subject = args.get("subject")
            limit = min(args.get("limit", 5), 20)
            query = select(Document.original_name).where(Document.user_id == user_id).order_by(Document.created_at.desc()).limit(limit)
            if subject:
                query = query.where(Document.subject.ilike(f"%{subject}%"))
            res = await db.execute(query)
            names = res.scalars().all()
            if not names:
                return json.dumps({"result": "Aucun document trouvé."})
            return json.dumps({"result": names})

        elif tool_name == "delete_document_by_name":
            filename = args.get("filename")
            if not filename:
                return json.dumps({"error": "Le nom du fichier est requis."})
            
            query = select(Document).where(Document.user_id == user_id, Document.original_name == filename)
            res = await db.execute(query)
            doc = res.scalar_one_or_none()
            
            if not doc:
                return json.dumps({"error": f"Aucun document nommé '{filename}' n'a été trouvé."})
            
            # Suppression dans ChromaDB
            try:
                delete_document_chunks(doc.id, user_id)
            except Exception:
                pass
                
            # Suppression dans SQL
            await db.delete(doc)
            await db.commit()
            
            return json.dumps({"result": f"Le document '{filename}' a été supprimé avec succès."})

        elif tool_name == "delete_documents_by_subject":
            subject = args.get("subject")
            query = select(Document).where(Document.user_id == user_id)
            if subject and subject.lower() != "non classé":
                query = query.where(Document.subject.ilike(f"%{subject}%"))
            else:
                # Assuming "Non classé" means subject is NULL or 'Non classé'
                query = query.where((Document.subject == None) | (Document.subject == "Non classé") | (Document.subject == ""))
            
            res = await db.execute(query)
            docs = res.scalars().all()
            
            if not docs:
                return json.dumps({"result": f"Aucun document trouvé pour la matière '{subject or 'Non classé'}'."})
            
            count = 0
            for doc in docs:
                try:
                    delete_document_chunks(doc.id, user_id)
                except Exception:
                    pass
                await db.delete(doc)
                count += 1
                
            await db.commit()
            return json.dumps({"result": f"{count} document(s) de la matière '{subject or 'Non classé'}' ont été supprimés avec succès."})

        elif tool_name == "generate_report":
            title = args.get("title", "Rapport Généré")
            content = args.get("content", "")
            
            import io
            import uuid
            from docx import Document as DocxDocument
            from storage.minio_client import minio_client
            from core.config import settings
            
            try:
                # Create the DOCX document
                doc = DocxDocument()
                doc.add_heading(title, 0)
                for paragraph in content.split("\n"):
                    if paragraph.strip():
                        doc.add_paragraph(paragraph.strip())
                
                # Save to in-memory buffer
                buffer = io.BytesIO()
                doc.save(buffer)
                buffer.seek(0)
                data = buffer.read()
                
                # Upload to MinIO
                unique_id = uuid.uuid4().hex[:6]
                filename = f"Rapport_{unique_id}.docx"
                object_name = f"{user_id}/reports/{filename}"
                
                bucket = settings.minio_bucket_processed
                minio_client.upload_file(
                    bucket=bucket,
                    object_name=object_name,
                    data=data,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
                # Generate presigned URL
                url = minio_client.get_presigned_url(
                    bucket=bucket,
                    object_name=object_name,
                    expires_hours=24
                )
                
                return json.dumps({
                    "result": f"Le rapport DOCX a été généré avec succès.",
                    "download_url": url,
                    "message_for_user": f"Voici le lien pour télécharger votre rapport : [Télécharger {filename}]({url})"
                })
            except Exception as e:
                return json.dumps({"error": f"Erreur lors de la génération du document DOCX : {str(e)}"})

        return json.dumps({"error": f"Failed to execute unknown tool: {tool_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
