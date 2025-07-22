"""QR Code generator module for URL shortening service"""
import io
from typing import BinaryIO
import qrcode
from qrcode.image.pil import PilImage
from PIL import Image


def generate_qr_code(data: str, size: str = "medium") -> BinaryIO:
    """
    Generate QR code for given data and return as binary stream
    
    Args:
        data: The data to encode in QR code (URL)
        size: Size of QR code ("small", "medium", "large")
    
    Returns:
        BinaryIO: PNG image data as binary stream
    """
    # Define size configurations
    size_configs = {
        "small": {"version": 1, "box_size": 6, "border": 2},
        "medium": {"version": 1, "box_size": 10, "border": 4},
        "large": {"version": 1, "box_size": 15, "border": 6}
    }
    
    config = size_configs.get(size, size_configs["medium"])
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=config["version"],  # Controls the size of the QR Code
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction
        box_size=config["box_size"],  # Size of each box in pixels
        border=config["border"],  # Border size in boxes
    )
    
    # Add data and optimize
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    qr_image: PilImage = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to PNG binary data
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format="PNG", optimize=True)
    img_buffer.seek(0)
    
    return img_buffer


def get_qr_code_dimensions(size: str = "medium") -> tuple[int, int]:
    """
    Get the dimensions of QR code for given size
    
    Args:
        size: Size of QR code ("small", "medium", "large")
        
    Returns:
        tuple: (width, height) in pixels
    """
    size_configs = {
        "small": {"version": 1, "box_size": 6, "border": 2},
        "medium": {"version": 1, "box_size": 10, "border": 4},
        "large": {"version": 1, "box_size": 15, "border": 6}
    }
    
    config = size_configs.get(size, size_configs["medium"])
    
    # QR Code version 1 is 21x21 modules
    modules = 21
    total_size = (modules + 2 * config["border"]) * config["box_size"]
    
    return (total_size, total_size)