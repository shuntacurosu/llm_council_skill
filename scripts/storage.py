"""Storage for conversation history."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


class ConversationStorage:
    """Manages conversation storage in JSON files."""
    
    def __init__(self, conversations_dir: Path):
        """
        Initialize conversation storage.
        
        Args:
            conversations_dir: Directory to store conversation files
        """
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_conversation_path(self, conversation_id: str) -> Path:
        """Get the file path for a conversation."""
        return self.conversations_dir / f"{conversation_id}.json"
    
    def create_conversation(self, conversation_id: str, title: str = "New Council Session") -> Dict[str, Any]:
        """
        Create a new conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            title: Title for the conversation
            
        Returns:
            New conversation dict
        """
        conversation = {
            "id": conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "title": title,
            "sessions": []
        }
        
        # Save to file
        path = self._get_conversation_path(conversation_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation from storage.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            Conversation dict or None if not found
        """
        path = self._get_conversation_path(conversation_id)
        
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_conversation(self, conversation: Dict[str, Any]):
        """
        Save a conversation to storage.
        
        Args:
            conversation: Conversation dict to save
        """
        path = self._get_conversation_path(conversation['id'])
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
    
    def add_session(
        self,
        conversation_id: str,
        user_query: str,
        council_results: Dict[str, Any],
        title: Optional[str] = None
    ):
        """
        Add a council session to a conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            user_query: The user's query
            council_results: Results from the council process
            title: Optional title for the conversation (auto-generated or user-provided)
        """
        conversation = self.get_conversation(conversation_id)
        
        if conversation is None:
            # Use provided title or default
            conversation = self.create_conversation(
                conversation_id, 
                title=title or "New Council Session"
            )
        elif title:
            # Update title if provided and this is an existing conversation
            conversation["title"] = title
        
        session = {
            "timestamp": datetime.utcnow().isoformat(),
            "query": user_query,
            "results": council_results
        }
        
        conversation["sessions"].append(session)
        self.save_conversation(conversation)
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        List all conversations (metadata only), sorted by newest first.
        
        Returns:
            List of conversation metadata dicts with 'index' field (1-based)
        """
        conversations = []
        
        for path in self.conversations_dir.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Council Session"),
                        "session_count": len(data.get("sessions", []))
                    })
            except Exception:
                pass  # Silently skip corrupted files
        
        # Sort by created_at (newest first)
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Add 1-based index for easy reference
        for i, conv in enumerate(conversations, 1):
            conv["index"] = i
        
        return conversations
    
    def get_conversation_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by its list index (1-based).
        
        Args:
            index: 1-based index from list_conversations()
            
        Returns:
            Full conversation dict or None if not found
        """
        conversations = self.list_conversations()
        
        if index < 1 or index > len(conversations):
            return None
        
        conversation_id = conversations[index - 1]["id"]
        return self.get_conversation(conversation_id)
    
    def get_conversation_id_by_index(self, index: int) -> Optional[str]:
        """
        Get a conversation ID by its list index (1-based).
        
        Args:
            index: 1-based index from list_conversations()
            
        Returns:
            Conversation ID or None if not found
        """
        conversations = self.list_conversations()
        
        if index < 1 or index > len(conversations):
            return None
        
        return conversations[index - 1]["id"]
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        Get the conversation history as a list of messages for context.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        conversation = self.get_conversation(conversation_id)
        
        if conversation is None:
            return []
        
        messages = []
        for session in conversation.get("sessions", []):
            # Add user query
            messages.append({
                "role": "user",
                "content": session.get("query", "")
            })
            
            # Add chairman's synthesis as assistant response
            results = session.get("results", {})
            stage3 = results.get("stage3", {})
            if stage3:
                messages.append({
                    "role": "assistant",
                    "content": stage3.get("response", "")
                })
        
        return messages
