from rq import SimpleWorker, Queue
from app.core.redis import redis_client

listen = ['render_queue']

if __name__ == '__main__':
    queues = [Queue(name, connection=redis_client) for name in listen]
    worker = SimpleWorker(queues, connection=redis_client)
    worker.work()