from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.core.cache import cache
from .models import Student
from .rate_limit import rate_limit
import redis
import json

r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

@api_view(['POST'])
def register_student(request):
    stu_id = request.data.get('stu_id')
    stu_name = request.data.get('stu_name')
    
    if not stu_id or not stu_name:
        return Response({'error': 'Missing data'}, status=400)
    
    
    student_payload = json.dumps({'stu_id': stu_id, 'stu_name': stu_name})

    # 2. Push it instantly to the Redis queue
    r.lpush('student_registration_queue', student_payload)
    
    # 3. Return an immediate response to the client
    return Response({'message': 'Registration queued successfully!'}, status=202)

# caching
@api_view(['GET'])
# 5 request in 1 minute 
@rate_limit(max_request=5, time_window=60)
def list_view(request):
    cache_key = 'students-data'

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Response({"message": cached_data})
    
    data = list(Student.objects.all().values('stu_id', 'stu_name'))
    
    cache.set(cache_key, data, 60 * 5)
    return Response({"message": data})

r = redis.Redis()
@api_view(['POST'])
def leaderBoard_add(request):
    user = request.data.get('user')
    score = request.data.get('score', 0)
    r.zadd('boardscore', {user: score})
    return Response({'message': 'Score added'})

@api_view(['GET'])
def leaderBoard_list(request):
    top_users = r.zrevrange('boardscore', 0, 4, withscores = True)
    return Response({'message': top_users})
