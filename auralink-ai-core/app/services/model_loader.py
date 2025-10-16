"""
AuraLink AIC Protocol - Production Model Loader
Loads pre-trained neural compression models for production use
"""

import os
import logging
import torch
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    Production-grade model loader for AIC compression models
    Handles model downloading, caching, and GPU loading
    """
    
    def __init__(self, model_dir: str = "/app/models", use_gpu: bool = True):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.device = torch.device("cuda" if (use_gpu and torch.cuda.is_available()) else "cpu")
        
        logger.info(f"ModelLoader initialized: device={self.device}, model_dir={self.model_dir}")
    
    def load_video_model(self, model_path: Optional[str] = None) -> torch.nn.Module:
        """
        Load video compression model
        
        Options:
        1. Load from local checkpoint if available
        2. Use pre-trained weights if provided
        3. Initialize with random weights (for development/training)
        """
        from .neural_models import VideoCompressionNet
        
        model = VideoCompressionNet(channels=3, latent_dim=64)
        
        # Try to load pre-trained weights
        if model_path and os.path.exists(model_path):
            logger.info(f"Loading video model from {model_path}")
            state_dict = torch.load(model_path, map_location=self.device)
            model.load_state_dict(state_dict)
            logger.info("Video model weights loaded successfully")
        else:
            # Check for auto-downloaded weights
            auto_path = self.model_dir / "video_compression_v1.pth"
            if auto_path.exists():
                logger.info(f"Loading auto-downloaded video model from {auto_path}")
                state_dict = torch.load(str(auto_path), map_location=self.device)
                model.load_state_dict(state_dict)
                logger.info("Video model weights loaded from cache")
            else:
                logger.warning(
                    "No pre-trained weights found for video model. "
                    "Using random initialization. "
                    "For production, provide trained weights or use pre-trained EnCodec."
                )
        
        model.to(self.device)
        model.eval()
        return model
    
    def load_audio_model(self, model_path: Optional[str] = None) -> torch.nn.Module:
        """
        Load audio compression model
        
        Options:
        1. Load from local checkpoint if available
        2. Use pre-trained EnCodec (Facebook's model)
        3. Initialize with random weights (for development/training)
        """
        from .neural_models import AudioCompressionNet
        
        model = AudioCompressionNet(sample_rate=48000)
        
        # Try to load pre-trained weights
        if model_path and os.path.exists(model_path):
            logger.info(f"Loading audio model from {model_path}")
            state_dict = torch.load(model_path, map_location=self.device)
            model.load_state_dict(state_dict)
            logger.info("Audio model weights loaded successfully")
        else:
            # Check for auto-downloaded weights
            auto_path = self.model_dir / "audio_compression_v1.pth"
            if auto_path.exists():
                logger.info(f"Loading auto-downloaded audio model from {auto_path}")
                state_dict = torch.load(str(auto_path), map_location=self.device)
                model.load_state_dict(state_dict)
                logger.info("Audio model weights loaded from cache")
            else:
                logger.warning(
                    "No pre-trained weights found for audio model. "
                    "Using random initialization. "
                    "For production, provide trained weights or use pre-trained EnCodec."
                )
        
        model.to(self.device)
        model.eval()
        return model
    
    def try_load_encodec(self) -> Optional[Dict]:
        """
        Try to load Facebook's EnCodec pre-trained model
        This provides production-quality compression out of the box
        
        Returns None if encodec is not installed
        """
        try:
            from encodec import EncodecModel
            from encodec.utils import convert_audio
            
            logger.info("Loading Facebook EnCodec pre-trained model...")
            
            # EnCodec 24kHz model (good balance of quality and speed)
            model = EncodecModel.encodec_model_24khz()
            model.to(self.device)
            model.eval()
            
            logger.info("EnCodec model loaded successfully (pre-trained)")
            
            return {
                'model': model,
                'convert_audio': convert_audio,
                'type': 'encodec',
                'sample_rate': 24000
            }
        except ImportError:
            logger.info(
                "EnCodec not available. Install with: pip install encodec. "
                "Falling back to custom models."
            )
            return None
        except Exception as e:
            logger.error(f"Failed to load EnCodec: {e}")
            return None
    
    def save_model(self, model: torch.nn.Module, name: str):
        """Save model weights to disk"""
        path = self.model_dir / f"{name}.pth"
        torch.save(model.state_dict(), path)
        logger.info(f"Model saved to {path}")
    
    def list_available_models(self) -> Dict[str, Path]:
        """List all available model files"""
        models = {}
        for file in self.model_dir.glob("*.pth"):
            models[file.stem] = file
        return models


# Global model loader instance
_model_loader: Optional[ModelLoader] = None


def get_model_loader(model_dir: str = "/app/models", use_gpu: bool = True) -> ModelLoader:
    """Get global model loader instance"""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader(model_dir, use_gpu)
    return _model_loader
