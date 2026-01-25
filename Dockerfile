# Python Sandbox Image for MCP Server Code Execution Mode
#
# This image includes common data science and visualization packages
# so they don't need to be installed at runtime.
#
# Build:
#   docker build -t python-sandbox:latest .
#   # or with Podman:
#   podman build -t python-sandbox:latest .
#
# Use:
#   Set MCP_BRIDGE_IMAGE=python-sandbox:latest in your environment
#   or in .vscode/mcp.json

FROM python:3.13-slim

# Install visualization and data science packages
RUN pip install --no-cache-dir \
    matplotlib \
    pillow \
    pandas \
    numpy \
    seaborn

# Set up non-root user (matches container security settings)
# The bridge runs with --user 65534:65534 (nobody)
RUN mkdir -p /workspace /projects && \
    chown -R 65534:65534 /workspace /projects

WORKDIR /workspace

# Default command (overridden by bridge)
CMD ["python"]
