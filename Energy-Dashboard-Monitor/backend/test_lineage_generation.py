"""
Test script for SAP AI Core Gemini 2.5 Pro integration.
Generates a "Hello World" SVG glyph and saves it.
"""

import os
import re
from sap_ai_client import SAPAIClient

# Try to import cairosvg for PNG conversion (optional)
try:
    from cairosvg import svg2png
    CAIROSVG_AVAILABLE = True
except (ImportError, OSError) as e:
    CAIROSVG_AVAILABLE = False
    svg2png = None  # type: ignore
    print(f"⚠️  cairosvg not available - will save SVG only ({type(e).__name__})")


def save_svg_as_png(svg_content: str, output_path: str) -> bool:
    """
    Convert SVG content to PNG and save to file.
    Requires Cairo library to be installed on the system.
    
    Args:
        svg_content: SVG string content
        output_path: Path to save PNG file
        
    Returns:
        True if successful, False otherwise
    """
    if not CAIROSVG_AVAILABLE:
        print("⚠️  PNG conversion skipped - cairosvg not available")
        print("   To enable PNG conversion, install Cairo:")
        print("   macOS: brew install cairo")
        print("   Ubuntu: sudo apt-get install libcairo2")
        return False
    
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert SVG to PNG
        svg2png(bytestring=svg_content.encode('utf-8'), write_to=output_path)
        
        print(f"✅ PNG saved successfully to: {output_path}")
        return True
    
    except Exception as e:
        print(f"❌ Error saving PNG: {e}")
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("IMAGE GENERATION TEST  |  Gemini 2.5 Pro")
    print("Prompt  : Hello-World glyph (SVG)")
    print("=" * 60)
    print()
    
    # Initialize SAP AI Client
    try:
        client = SAPAIClient()
        print("✅ SAP AI Client initialized successfully")
    except ValueError as e:
        print(f"❌ Failed to initialize client: {e}")
        return
    
    # Define the prompt
    HELLO_WORLD_PROMPT = """
Design a stylised "Hello, World!" glyph as a standalone SVG image.

Specifications:
- Dimensions      : 480 × 200 px (viewBox="0 0 480 200")
- Background      : deep navy  (#0d1117)
- Primary text    : bold, modern sans-serif, fill #39ff14 (neon green)
- Glow effect     : use a <filter> with feGaussianBlur to add a soft green glow
- Accent elements : a thin horizontal rule above and below the text, same neon-green colour
- Text            : centred horizontally and vertically on the canvas

Return ONLY the SVG — starting with <svg and ending with </svg>.
"""
    
    # Generate image content
    print("🎨 Generating Hello World glyph...")
    result = client.generate_image_content(
        prompt=HELLO_WORLD_PROMPT,
        model_name="gemini-2.5-pro",
        temperature=0.7
    )
    
    if not result:
        print("❌ Failed to generate content")
        return
    
    # Extract SVG
    svg_content = client.extract_svg_from_response(result)
    
    if not svg_content:
        print("❌ No SVG content found in response")
        return
    
    # Check if it's valid SVG
    if not svg_content.strip().startswith('<svg'):
        print("⚠️  Response doesn't appear to be valid SVG:")
        print(svg_content[:500])
        return
    
    print("✅ SVG glyph generated successfully")
    print()
    print("── Raw SVG (first 500 chars) ──")
    print(svg_content[:500])
    print()
    
    # Save SVG to file
    svg_output_path = "../data/lineage-outputs/hello_world.svg"
    try:
        os.makedirs(os.path.dirname(svg_output_path), exist_ok=True)
        with open(svg_output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        print(f"✅ SVG saved to: {svg_output_path}")
    except Exception as e:
        print(f"❌ Error saving SVG: {e}")
    
    # Convert and save as PNG
    png_output_path = "../data/lineage-outputs/hello_world.png"
    if save_svg_as_png(svg_content, png_output_path):
        print(f"✅ Test completed successfully!")
        print(f"   SVG: {svg_output_path}")
        print(f"   PNG: {png_output_path}")
    
    # Display token usage
    usage = client.get_token_usage(result)
    if usage:
        print()
        print("── Token usage ──")
        print(f"  Prompt     : {usage.get('prompt_tokens', 'N/A')}")
        print(f"  Completion : {usage.get('completion_tokens', 'N/A')}")
        print(f"  Total      : {usage.get('total_tokens', 'N/A')}")


if __name__ == "__main__":
    main()

# Made with Bob
