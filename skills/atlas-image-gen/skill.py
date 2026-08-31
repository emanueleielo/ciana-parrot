"""Agent tools for Atlas Cloud image generation."""

import os
import urllib.error
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from langchain_core.tools import tool

try:
    from .atlas_client import DEFAULT_MODEL, generate_image
except ImportError:
    client_path = Path(__file__).with_name("atlas_client.py")
    client_spec = spec_from_file_location("atlas_image_client", client_path)
    if client_spec is None or client_spec.loader is None:
        raise ImportError(f"Unable to load Atlas client from {client_path}")
    client_module = module_from_spec(client_spec)
    client_spec.loader.exec_module(client_module)
    DEFAULT_MODEL = client_module.DEFAULT_MODEL
    generate_image = client_module.generate_image


@tool
def generate_atlas_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    size: str = "1024*1024",
) -> str:
    """Generate one image with Atlas Cloud and return the output URL.

    Args:
        prompt: Detailed text description of the image to generate.
        model: Exact Atlas Cloud text-to-image model ID.
        size: Model-supported output size, for example 1024*1024.
    """
    api_key = os.environ.get("ATLASCLOUD_API_KEY", "").strip()
    if not api_key:
        return "Error: ATLASCLOUD_API_KEY is not set"
    try:
        return generate_image(api_key, prompt, model, size)
    except (RuntimeError, urllib.error.URLError) as exc:
        return f"Error: {exc}"
