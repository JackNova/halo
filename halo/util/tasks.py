import logging, time
from datetime import datetime, timedelta
from celery.utils.log import get_task_logger

logger = get_task_logger('tasks')

def schedule_entities(query, count, task_func, interval_time,
                      args=[], kwargs={}, ttl=60*60):
    """interval_time can be a timedelta or number of seconds.
    """
    logging.info('schedule entities: %s' % count)
    if not count:
        return

    if isinstance(interval_time, timedelta):
        interval_time = interval_time.total_seconds()

    # delay between each task
    between_delay = interval_time / float(count)
    now = datetime.now()

    # this might be be made more efficient by pagination and raw sql
    for i, entity in enumerate(query):
        delay = i*between_delay
        logging.info('schedule entity update in %ss: %s' % \
                     (delay, task_func))

        task_func(
            entity,
            eta=now+timedelta(seconds=delay),
            #countdown=delay, # the countdown argument only uses seconds precision
            # expires is given as seconds after task publish
            expires=ttl,
            #task_id='update-%s' % account.id,
        )
        # cooperative yield so as to not block process
        time.sleep(0)
