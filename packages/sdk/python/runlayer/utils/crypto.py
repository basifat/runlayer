"""
Cryptographic utilities for RunLayer SDK

Provides Ed25519 digital signatures for proof authenticity:
- Key generation and management
- Data signing and verification
- Secure key storage
"""

import base64
import os
from pathlib import Path
from typing import Tuple, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .logging import get_logger

logger = get_logger(__name__)


class KeyManager:
    """Manages Ed25519 keys for proof signing."""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.private_key_path = workspace_path / "private_key.pem"
        self.public_key_path = workspace_path / "public_key.pem"
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
    
    def ensure_keys_exist(self) -> None:
        """Ensure Ed25519 key pair exists, generate if not."""
        if not self.private_key_path.exists() or not self.public_key_path.exists():
            logger.info("Generating new Ed25519 key pair", workspace=str(self.workspace_path))
            self._generate_key_pair()
    
    def _generate_key_pair(self) -> None:
        """Generate and save new Ed25519 key pair."""
        # Generate private key
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Ensure directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(self.private_key_path, 'wb') as f:
            f.write(private_pem)
        
        # Set restrictive permissions on private key
        os.chmod(self.private_key_path, 0o600)
        
        # Save public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        with open(self.public_key_path, 'wb') as f:
            f.write(public_pem)
        
        logger.info("Ed25519 key pair generated successfully")
    
    def get_private_key(self) -> Ed25519PrivateKey:
        """Get the private key, loading if necessary."""
        if self._private_key is None:
            self.ensure_keys_exist()
            
            with open(self.private_key_path, 'rb') as f:
                private_pem = f.read()
            
            self._private_key = serialization.load_pem_private_key(
                private_pem,
                password=None
            )
        
        return self._private_key
    
    def get_public_key(self) -> Ed25519PublicKey:
        """Get the public key, loading if necessary."""
        if self._public_key is None:
            self.ensure_keys_exist()
            
            with open(self.public_key_path, 'rb') as f:
                public_pem = f.read()
            
            self._public_key = serialization.load_pem_public_key(public_pem)
        
        return self._public_key
    
    def get_public_key_bytes(self) -> bytes:
        """Get public key as raw bytes."""
        public_key = self.get_public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )


def generate_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 key pair.
    
    Returns:
        Tuple of (private_key_pem, public_key_pem) as base64 strings
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Return as base64 strings
    return (
        base64.b64encode(private_pem).decode('utf-8'),
        base64.b64encode(public_pem).decode('utf-8')
    )


def sign_data(data: str, private_key: Ed25519PrivateKey) -> str:
    """
    Sign data with Ed25519 private key.
    
    Args:
        data: Data to sign (as string)
        private_key: Ed25519 private key
        
    Returns:
        Base64-encoded signature
    """
    try:
        signature = private_key.sign(data.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        logger.error("Failed to sign data", error=str(e))
        raise


def verify_signature(data: str, signature: str, public_key: Ed25519PublicKey) -> bool:
    """
    Verify Ed25519 signature.
    
    Args:
        data: Original data (as string)
        signature: Base64-encoded signature
        public_key: Ed25519 public key
        
    Returns:
        True if signature is valid
    """
    try:
        signature_bytes = base64.b64decode(signature.encode('utf-8'))
        public_key.verify(signature_bytes, data.encode('utf-8'))
        return True
    except (InvalidSignature, Exception) as e:
        logger.debug("Signature verification failed", error=str(e))
        return False


def load_private_key_from_pem(pem_data: str) -> Ed25519PrivateKey:
    """
    Load Ed25519 private key from PEM string.
    
    Args:
        pem_data: PEM-encoded private key
        
    Returns:
        Ed25519PrivateKey instance
    """
    pem_bytes = base64.b64decode(pem_data.encode('utf-8'))
    return serialization.load_pem_private_key(pem_bytes, password=None)


def load_public_key_from_pem(pem_data: str) -> Ed25519PublicKey:
    """
    Load Ed25519 public key from PEM string.
    
    Args:
        pem_data: PEM-encoded public key
        
    Returns:
        Ed25519PublicKey instance
    """
    pem_bytes = base64.b64decode(pem_data.encode('utf-8'))
    return serialization.load_pem_public_key(pem_bytes)
