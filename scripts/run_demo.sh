#!/bin/bash

# OCR Document Processing Demo Runner

echo "🚀 Starting OCR Document Processing Demo..."

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start API server in background
echo "🔧 Starting API server..."
python -m src.api.main &
API_PID=$!

# Wait for API to start
echo "Waiting for API to start..."
sleep 5

# Check if API is running
curl -s http://localhost:8000/health > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ API is running"
else
    echo "⚠️  API health check failed but continuing..."
fi

# Start Streamlit app
echo "🎨 Starting Streamlit app..."
python -m streamlit run streamlit_app.py --server.port 8501 &
STREAMLIT_PID=$!

echo ""
echo "==============================================="
echo "🎉 Demo is running!"
echo "==============================================="
echo "📊 Streamlit UI: http://localhost:8501"
echo "📚 API Docs: http://localhost:8000/docs"
echo "❤️  Health Check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"
echo "==============================================="

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $API_PID 2>/dev/null
    kill $STREAMLIT_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup INT

# Wait for processes
wait $API_PID $STREAMLIT_PID