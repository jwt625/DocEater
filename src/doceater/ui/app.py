"""Gradio web UI for DocEater."""

import json
from typing import Any

import gradio as gr
import httpx
import pandas as pd

from .config import API_BASE_URL, API_KEY


def make_request(
    method: str, endpoint: str, data: dict[str, Any] | None = None, files: dict | None = None
) -> dict[str, Any]:
    """Make HTTP request to DocEater API."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"X-API-Key": API_KEY}
    
    try:
        with httpx.Client(timeout=60.0) as client:
            if method == "GET":
                response = client.get(url, headers=headers, params=data)
            elif method == "POST":
                if files:
                    response = client.post(url, headers=headers, data=data, files=files)
                else:
                    headers["Content-Type"] = "application/json"
                    response = client.post(url, headers=headers, json=data)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}


def search_documents(
    query: str,
    top_k: int,
    similarity_threshold: float,
    include_text: bool,
    include_images: bool,
) -> tuple[str, pd.DataFrame]:
    """Search documents using semantic search."""
    if not query.strip():
        return "Please enter a search query.", pd.DataFrame()
    
    data = {
        "query": query,
        "top_k": top_k,
        "similarity_threshold": similarity_threshold,
        "include_text": include_text,
        "include_images": include_images,
    }
    
    result = make_request("POST", "/api/v1/search", data=data)
    
    if "error" in result:
        return f"Error: {result['error']}", pd.DataFrame()
    
    if not result.get("results"):
        return f"No results found for '{query}'", pd.DataFrame()
    
    # Format results as DataFrame
    rows = []
    for r in result["results"]:
        rows.append({
            "Type": r["content_type"],
            "Document": r["document_filename"],
            "Content": r["content"][:100] + "..." if len(r["content"]) > 100 else r["content"],
            "Similarity": f"{r['similarity_score']:.4f}",
            "Page": r.get("page_number", "N/A"),
        })
    
    df = pd.DataFrame(rows)
    summary = (
        f"Found {result['total_results']} results in {result['search_time_ms']:.0f}ms\n"
        f"Text: {result['text_results']}, Images: {result['image_results']}"
    )
    
    return summary, df


def list_documents(page: int, page_size: int, status_filter: str) -> tuple[str, pd.DataFrame]:
    """List documents with pagination."""
    params = {"page": page, "page_size": page_size}
    if status_filter != "all":
        params["status_filter"] = status_filter
    
    result = make_request("GET", "/api/v1/documents", data=params)
    
    if "error" in result:
        return f"Error: {result['error']}", pd.DataFrame()
    
    if not result.get("documents"):
        return "No documents found.", pd.DataFrame()
    
    # Format as DataFrame
    rows = []
    for doc in result["documents"]:
        rows.append({
            "Filename": doc["filename"],
            "Status": doc["status"],
            "Size (MB)": f"{doc['file_size'] / 1024 / 1024:.2f}",
            "Text Emb": doc.get("text_embedding_count", 0),
            "Image Emb": doc.get("image_embedding_count", 0),
            "Created": doc["created_at"][:10],
        })
    
    df = pd.DataFrame(rows)
    summary = f"Showing page {result['page']} of {result['total']} total documents"
    
    return summary, df


def upload_document(file, description: str) -> str:
    """Upload a document to DocEater."""
    if file is None:
        return "Please select a file to upload."
    
    try:
        with open(file.name, "rb") as f:
            files = {"file": (file.name.split("/")[-1], f, "application/pdf")}
            data = {"description": description} if description else {}
            result = make_request("POST", "/api/v1/documents/upload", data=data, files=files)
        
        if "error" in result:
            return f"Upload failed: {result['error']}"
        
        return (
            f"✓ Upload successful!\n"
            f"Document: {result['filename']}\n"
            f"Status: {result['status']}\n"
            f"ID: {result['id']}"
        )
    except Exception as e:
        return f"Upload failed: {str(e)}"


def get_stats() -> str:
    """Get system statistics."""
    result = make_request("GET", "/api/v1/stats")
    
    if "error" in result:
        return f"Error: {result['error']}"
    
    return (
        f"📊 System Statistics\n\n"
        f"Documents: {result['total_documents']} total, "
        f"{result['processing_documents']} processing, "
        f"{result['failed_documents']} failed\n"
        f"Embeddings: {result['total_text_embeddings']} text, "
        f"{result['total_image_embeddings']} images\n"
        f"Images: {result['total_images']} stored\n"
        f"Storage: {result['total_storage_mb']:.2f} MB total"
    )


def get_health() -> str:
    """Get system health status."""
    result = make_request("GET", "/api/v1/health")
    
    if "error" in result:
        return f"Error: {result['error']}"
    
    status_emoji = "✓" if result["status"] == "healthy" else "✗"
    return (
        f"{status_emoji} System Status: {result['status'].upper()}\n\n"
        f"Database: {result['database']}\n"
        f"Embedding Model: {result['embedding_model']}\n"
        f"Disk Space: {result['disk_space']}\n"
        f"Uptime: {result['uptime_seconds'] / 3600:.1f} hours\n"
        f"Memory: {result['memory_usage_mb']:.1f} MB"
    )


# Build Gradio Interface
with gr.Blocks(title="DocEater", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🍽️ DocEater - Document Search & Management")
    gr.Markdown("**Status:** Connected")
    
    with gr.Tabs():
        # Search Tab
        with gr.Tab("🔍 Search"):
            with gr.Row():
                with gr.Column(scale=1):
                    search_query = gr.Textbox(
                        label="Search Query",
                        placeholder="Enter your search query...",
                        lines=2,
                    )
                    with gr.Row():
                        top_k = gr.Slider(1, 20, value=5, step=1, label="Top K Results")
                        similarity = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="Similarity Threshold")
                    with gr.Row():
                        include_text = gr.Checkbox(value=True, label="Include Text")
                        include_images = gr.Checkbox(value=True, label="Include Images")
                    search_btn = gr.Button("Search", variant="primary")
                
                with gr.Column(scale=2):
                    search_summary = gr.Textbox(label="Summary", lines=2)
                    search_results = gr.Dataframe(
                        label="Results",
                        wrap=True,
                        interactive=False,
                    )
            
            search_btn.click(
                search_documents,
                inputs=[search_query, top_k, similarity, include_text, include_images],
                outputs=[search_summary, search_results],
            )
        
        # Documents Tab
        with gr.Tab("📄 Documents"):
            with gr.Row():
                page_num = gr.Number(value=1, label="Page", precision=0)
                page_size = gr.Slider(5, 50, value=20, step=5, label="Page Size")
                status_filter = gr.Dropdown(
                    choices=["all", "pending", "processing", "completed", "failed"],
                    value="all",
                    label="Status Filter",
                )
                list_btn = gr.Button("Refresh", variant="secondary")
            
            doc_summary = gr.Textbox(label="Summary", lines=1)
            doc_list = gr.Dataframe(label="Documents", wrap=True, interactive=False)
            
            list_btn.click(
                list_documents,
                inputs=[page_num, page_size, status_filter],
                outputs=[doc_summary, doc_list],
            )
            
            # Auto-load on tab open
            app.load(
                list_documents,
                inputs=[page_num, page_size, status_filter],
                outputs=[doc_summary, doc_list],
            )
        
        # Upload Tab
        with gr.Tab("⬆️ Upload"):
            with gr.Row():
                with gr.Column():
                    upload_file = gr.File(label="Select Document", file_types=[".pdf"])
                    upload_desc = gr.Textbox(
                        label="Description (optional)",
                        placeholder="Enter document description...",
                        lines=2,
                    )
                    upload_btn = gr.Button("Upload", variant="primary")
                
                with gr.Column():
                    upload_status = gr.Textbox(label="Upload Status", lines=6)
            
            upload_btn.click(
                upload_document,
                inputs=[upload_file, upload_desc],
                outputs=upload_status,
            )
        
        # System Tab
        with gr.Tab("⚙️ System"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Health Status")
                    health_output = gr.Textbox(label="Health", lines=8)
                    health_btn = gr.Button("Check Health", variant="secondary")
                
                with gr.Column():
                    gr.Markdown("### Statistics")
                    stats_output = gr.Textbox(label="Stats", lines=8)
                    stats_btn = gr.Button("Get Stats", variant="secondary")
            
            health_btn.click(get_health, outputs=health_output)
            stats_btn.click(get_stats, outputs=stats_output)
            
            # Auto-load on tab open
            app.load(get_health, outputs=health_output)
            app.load(get_stats, outputs=stats_output)


def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    """Launch the Gradio app."""
    app.launch(server_name=host, server_port=port, share=share)


if __name__ == "__main__":
    from .config import UI_HOST, UI_PORT, UI_SHARE
    launch(UI_HOST, UI_PORT, UI_SHARE)

