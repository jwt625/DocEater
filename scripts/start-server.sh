#!/bin/bash
# DocEater API Server Startup Script

set -e

# Configuration
HOST="0.0.0.0"
PORT="8000"
WORKERS="2"
LOG_FILE="logs/doceat.log"

# Create logs directory
mkdir -p logs

# Check if server is already running
if pgrep -f "doceat serve" > /dev/null; then
    echo "❌ DocEater server is already running"
    echo "   Use 'pkill -f \"doceat serve\"' to stop it first"
    exit 1
fi

# Start server based on mode
case "${1:-prod}" in
    "dev")
        echo "🚀 Starting DocEater in development mode..."
        uv run doceat serve --host $HOST --port $PORT --reload
        ;;
    "prod")
        echo "🚀 Starting DocEater in production mode..."
        nohup uv run doceat serve --host $HOST --port $PORT --workers $WORKERS > $LOG_FILE 2>&1 &
        PID=$!
        echo "✅ Server started with PID: $PID"
        echo "📊 API Documentation: http://localhost:$PORT/docs"
        echo "📋 Health Check: http://localhost:$PORT/api/v1/health"
        echo "📄 Logs: tail -f $LOG_FILE"
        ;;
    "stop")
        echo "🛑 Stopping DocEater server..."
        pkill -f "doceat serve" && echo "✅ Server stopped" || echo "❌ No server running"
        ;;
    "status")
        if pgrep -f "doceat serve" > /dev/null; then
            echo "✅ DocEater server is running"
            curl -s http://localhost:$PORT/api/v1/health | jq '.status' 2>/dev/null || echo "Health check failed"
        else
            echo "❌ DocEater server is not running"
        fi
        ;;
    *)
        echo "Usage: $0 [dev|prod|stop|status]"
        echo "  dev    - Start in development mode (foreground)"
        echo "  prod   - Start in production mode (background)"
        echo "  stop   - Stop the server"
        echo "  status - Check server status"
        exit 1
        ;;
esac
