class BroadcastState:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._is_broadcasting = False
            cls._instance._messages = []
        return cls._instance
    
    @property
    def is_broadcasting(self):
        return self._is_broadcasting
    
    @is_broadcasting.setter 
    def is_broadcasting(self, value: bool):
        self._is_broadcasting = value
        if not value:
            self._messages.clear()
    
    def add_message(self, message):
        """Add message to broadcast queue"""
        if self._is_broadcasting:
            self._messages.append(message)
    
    def get_messages(self):
        """Get collected messages and clear queue"""
        messages = self._messages.copy()
        self._messages.clear()
        return messages

# Create singleton instance
broadcast_state = BroadcastState()