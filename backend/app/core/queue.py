from rq import Queue
from app.core.redis import redis_client

render_queue = Queue("render_queue", connection=redis_client)
