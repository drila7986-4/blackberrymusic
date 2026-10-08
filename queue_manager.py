queues = {}


def get_queue(chat_id):
    return queues.setdefault(chat_id, [])


def add_to_queue(chat_id, item):
    get_queue(chat_id).append(item)


def pop_next(chat_id):
    q = get_queue(chat_id)
    if q:
        return q.pop(0)
    return None


def clear_queue(chat_id):
    queues[chat_id] = []
