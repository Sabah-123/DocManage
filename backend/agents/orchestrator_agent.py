import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from groq import Groq

from core.config import settings
from agents.tools import get_tools_schema, execute_tool
from agents.rag_agent import query_documents, summarize_document

logger = logging.getLogger(__name__)

class MCPServer:
    """
    MCP SERVER: Meta-Agent Orchestrateur
    Passe d'un système multi-agents séquentiel à un système agentique autonome
    avec raisonnement Chain-of-Thought (CoT), planification dynamique et gestion d'erreurs adaptative.
    """
    
    def __init__(self, db_session: AsyncSession, user_id: int):
        self.db = db_session
        self.user_id = user_id
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        
        # Outils disponibles pour l'orchestrateur (combinaison des outils existants et des agents)
        self.tools_schema = get_tools_schema()
        self._add_agent_tools()

    def _add_agent_tools(self):
        """Ajoute dynamiquement les capacités des autres agents comme outils pour le MCP Server."""
        self.tools_schema.extend([
            {
                "type": "function",
                "function": {
                    "name": "rag_query",
                    "description": "Faire une recherche sémantique dans les documents (RAG) pour répondre à une question sur le contenu des documents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "La question posée par l'utilisateur concernant le contenu des documents."
                            },
                            "document_id": {
                                "type": "integer",
                                "description": "L'ID d'un document spécifique pour filtrer la recherche. Laisser vide pour chercher dans tous les documents de l'utilisateur."
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_doc",
                    "description": "Générer un résumé complet et structuré d'un document spécifique, ou extraire le contenu global d'un document/image.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "integer",
                                "description": "L'ID du document à résumer."
                            }
                        },
                        "required": ["document_id"]
                    }
                }
            }
        ])

    async def _execute_mcp_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Exécute l'outil ou l'agent demandé par le modèle LLM."""
        try:
            logger.info(f"[MCP SERVER] Exécution de l'outil: {tool_name} avec args: {args}")
            
            if tool_name == "rag_query":
                res = query_documents(
                    question=args.get("question"),
                    user_id=self.user_id,
                    document_id=args.get("document_id")
                )
                # On ne retourne que la réponse textuelle à l'orchestrateur pour qu'il raisonne dessus
                return json.dumps({"result": res["answer"]}, ensure_ascii=False)
                
            elif tool_name == "summarize_doc":
                res = summarize_document(
                    document_id=args.get("document_id"),
                    user_id=self.user_id
                )
                return json.dumps({"result": res}, ensure_ascii=False)
            
            else:
                # Outils de base de données et autres actions (tools.py)
                return await execute_tool(tool_name, args, self.user_id, self.db)
                
        except Exception as e:
            logger.error(f"[MCP SERVER] Erreur lors de l'exécution de {tool_name}: {e}")
            # Gestion d'erreur adaptative : on informe le LLM de l'erreur pour qu'il ajuste son plan
            return json.dumps({
                "error": str(e), 
                "message": f"Une erreur est survenue avec {tool_name}. Veuillez analyser l'erreur et adapter votre plan (par exemple, utiliser un autre outil ou demander des précisions)."
            }, ensure_ascii=False)

    async def process_task(self, task: str, history: List[Dict[str, str]] = None) -> str:
        """
        Analyse la tâche et décide dynamiquement quels agents/outils mobiliser
        en utilisant un processus itératif de raisonnement (ReAct loop).
        """
        logger.info(f"[MCP SERVER] Nouvelle tâche reçue: {task}")
        
        system_prompt = """Tu es le 'MCP SERVER', un méta-agent orchestrateur ultra-intelligent.
Ton rôle est d'analyser chaque tâche complexe de l'utilisateur, de planifier les étapes nécessaires, et de mobiliser dynamiquement les agents/outils appropriés.

PROCESSUS DE RAISONNEMENT (Chain-of-Thought) :
Tu fonctionnes de manière autonome. Avant d'utiliser un outil ou de donner une réponse finale, tu dois TOUJOURS utiliser une étape de réflexion interne structurée.
Si la tâche nécessite plusieurs étapes (ex: chercher une information puis générer un rapport), exécute-les séquentiellement en appelant les outils l'un après l'autre.

RÈGLES D'OR :
1. Planification : Identifie clairement le but de l'utilisateur et les outils requis.
2. Adaptabilité : Si un outil retourne une erreur, ne t'arrête pas. Analyse l'erreur et trouve un plan alternatif.
3. Synthèse : Une fois toutes les informations récoltées via tes agents, fournis une réponse finale riche et complète en français.
4. RAG : Utilise 'rag_query' ou 'summarize_doc' pour lire le contenu des documents (MÊME LES IMAGES ! Le texte des images est extrait par OCR, donc traite les images comme des documents texte normaux. Ne dis JAMAIS que tu ne peux pas lire d'images).
5. Base de données : Utilise les autres outils pour lister, compter, ou manipuler les documents.

Commence l'exécution de la tâche maintenant.
"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            # On intègre l'historique de la conversation pour le contexte
            messages.extend(history)
            
        messages.append({"role": "user", "content": f"Tâche à accomplir : {task}"})

        max_iterations = 7  # Limite pour éviter les boucles infinies de l'agent
        
        for iteration in range(max_iterations):
            logger.info(f"[MCP SERVER] Itération {iteration + 1}/{max_iterations}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools_schema,
                tool_choice="auto",
                temperature=0.2 # Température basse pour privilégier la logique et la cohérence
            )
            
            msg = response.choices[0].message
            
            # On ajoute le message de l'assistant (avec ou sans appels d'outils) à l'historique
            messages.append(msg)
            
            # Si l'agent n'a pas appelé d'outils, cela signifie qu'il a terminé son raisonnement et fournit la réponse finale
            if not msg.tool_calls:
                logger.info("[MCP SERVER] Tâche terminée avec succès par l'orchestrateur.")
                return msg.content
                
            # Si l'agent demande l'exécution d'outils, on les traite
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args_str = tool_call.function.arguments
                
                try:
                    fn_args = json.loads(fn_args_str) if fn_args_str else {}
                except json.JSONDecodeError:
                    fn_args = {}
                    
                # Exécution de l'outil / agent spécialisé
                result_str = await self._execute_mcp_tool(fn_name, fn_args)
                
                # Feedback de l'outil réinjecté dans le contexte de l'agent
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": result_str
                })

        # Gestion du cas où le nombre maximal d'itérations est atteint
        logger.warning("[MCP SERVER] Limite d'itérations atteinte. Interruption forcée de la boucle ReAct.")
        return "Désolé, la tâche s'est révélée trop complexe et a dépassé ma limite d'itérations internes. Pouvez-vous la simplifier ou la diviser en sous-tâches ?"

    async def process_task_stream(self, task: str, history: List[Dict[str, str]] = None):
        """
        Version streaming de l'orchestrateur.
        Yield des dictionnaires avec 'token' pour le streaming SSE.
        """
        logger.info(f"[MCP SERVER STREAM] Nouvelle tâche reçue: {task}")
        
        system_prompt = """Tu es le 'MCP SERVER', un méta-agent orchestrateur intelligent.
Rôle: Analyser, planifier et mobiliser les agents/outils appropriés.
Règles: 
1. Utilise 'rag_query' ou 'summarize_doc' si on pose une question sur le contenu documentaire (MÊME LES IMAGES ! Le texte des images est extrait par OCR, tu DOIS le lire).
2. Utilise les autres outils pour gérer/manipuler la base de données.
3. Ne divulgue pas tes pensées internes. Si tu utilises un outil, fais-le silencieusement.
4. Une fois l'information obtenue, fournis une réponse claire et synthétique en français.
5. Si tu as déjà toutes les informations, réponds directement sans utiliser d'outil.
"""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": f"Tâche : {task}"})

        max_iterations = 5
        
        for iteration in range(max_iterations):
            logger.info(f"[MCP SERVER STREAM] Itération {iteration + 1}/{max_iterations}")
            
            # Utiliser le stream si on veut, mais pour le ReAct, le non-stream est plus sûr pour lire les tool_calls.
            # Cependant, à la dernière itération ou s'il n'y a pas d'outils, on veut streamer la réponse.
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools_schema,
                tool_choice="auto",
                temperature=0.2
            )
            
            msg = response.choices[0].message
            
            if not msg.tool_calls:
                # C'est la réponse finale. Si elle a déjà du contenu, on peut le streamer ou le rendre.
                if msg.content:
                    # On stream le contenu existant pour garder la cohérence de l'interface
                    yield {"token": msg.content}
                return
                
            # Traitement des outils
            messages.append(msg)
            
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args_str = tool_call.function.arguments
                
                try:
                    fn_args = json.loads(fn_args_str) if fn_args_str else {}
                except json.JSONDecodeError:
                    fn_args = {}
                    
                result_str = await self._execute_mcp_tool(fn_name, fn_args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": result_str
                })

        yield {"token": "\n\nDésolé, la tâche est trop complexe (limite d'itérations atteinte)."}
