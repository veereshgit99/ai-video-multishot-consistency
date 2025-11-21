from rq import SimpleWorker, Queue
from app.core.redis import redis_client

listen = ['render_queue']

if __name__ == '__main__':
    # Pre-warm CLIP model to avoid first-request slowness
    print("[Worker] Pre-warming CLIP model...")
    from app.services.embedding import _get_clip_model
    _get_clip_model()  # Load model once at worker startup
    print("[Worker] CLIP model ready!")
    
    queues = [Queue(name, connection=redis_client) for name in listen]
    worker = SimpleWorker(queues, connection=redis_client)
    print(f"[Worker] Listening on queues: {listen}")
    worker.work()