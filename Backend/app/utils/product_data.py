

def create_text(product: dict) -> str:
    """
    Create a text representation of the product for embedding.
    """
    text = f"Title: {product.get('title', '')}\n"
    text += f"Description: {product.get('description', '')}\n"
    text += f"Category: {product.get('category', '')}\n"
    text += f"Price: {product.get('price', '')}\n"
    text += f"Rating: {product.get('rating', '')}\n"
    text += f"Tags: {', '.join(product.get('tags', []))}\n"
    return text