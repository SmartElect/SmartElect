from voting.models import Election


def current_election(request):
    return {
        'current_election': Election.objects.get_current_election(),
    }
