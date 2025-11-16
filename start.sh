#!/bin/bash
# Quick start script for RAG API

set -e

echo "🚀 Building Code RAG API - Quick Start"
echo "======================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and set your:"
    echo "   - OPENAI_API_KEY"
    echo "   - POSTGRES_PASSWORD"
    echo ""
    read -p "Press Enter after you've updated .env, or Ctrl+C to exit..."
fi

# Start services
echo ""
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "🏥 Checking API health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is healthy!"
else
    echo "❌ API is not responding. Check logs with: docker-compose logs -f rag-api"
    exit 1
fi

# Show next steps
echo ""
echo "✅ RAG API is running!"
echo ""
echo "📍 API URL: http://localhost:8000"
echo "📍 Health: http://localhost:8000/health"
echo "📍 Docs: http://localhost:8000/docs"
echo ""
echo "🔧 Next steps:"
echo "   1. Ingest documents: python -m rag.scripts.ingest_document path/to/doc.json"
echo "   2. Test query: curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' -d '{\"query\":\"test\"}'"
echo "   3. For LibreChat: Copy librechat.yaml to LibreChat directory"
echo ""
echo "📚 See DEPLOYMENT.md for complete documentation"
echo ""
echo "🛑 To stop: docker-compose down"
