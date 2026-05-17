from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.core.cache import cache
from .models import Student
from .rate_limit import rate_limit
# caching
@api_view(['GET'])
@rate_limit(max_request=5, time_window=60)
def list_view(request):
    cache_key = 'students-data'

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Response({"message": cached_data})
    
    data = list(Student.objects.all().values('stu_id', 'stu_name'))
    
    cache.set(cache_key, data, 60 * 5)
    return Response({"message": data})