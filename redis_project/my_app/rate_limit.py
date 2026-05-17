import redis
from functools import wraps
from rest_framework.response import Response
from rest_framework.exceptions import Throttled

# Connect to Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

def rate_limit(max_request: int, time_window: int):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = args[0] if hasattr(args[0], 'user') else args[1]
            
            client_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')
            endpoint = request.path
            redis_key = f'rate_limit:{client_id}:{endpoint}'

            current_requests = redis_client.get(redis_key)

            if current_requests is None:
                redis_client.set(redis_key, 1, ex=time_window)
            elif int(current_requests) < max_request:
                redis_client.incr(redis_key)
            else:
                retry_after = redis_client.ttl(redis_key)
                raise Throttled(detail=f"Rate limit exceeded. Try again after {retry_after} seconds.")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator