from prompt_toolkit import prompt
import sys

from educelab import hercdb
from educelab.hercdb import config


def record_sort(r):
    ret = r['cr']['human_name']
    if r['pz'] is not None:
        ret += ', ' + r['pz']['human_name']
    return ret


def record_name(record):
    pherc = record['ph']['human_name']
    cr = record['cr']['human_name']
    is_scorze = 'Scorze' in cr or 'Scorza' in cr
    pz = ''
    if record['pz'] is not None:
        pz = f", Pz. {record['pz']['human_name']}"
    return f'P.Herc. {pherc}, {"" if is_scorze else "Cr. "}{cr}{pz}'


def main():
    # get missing login information
    config.request_required()

    # connect to the server
    db = hercdb.connect()
    status = db.verify_connection()
    print(f'Connected: {status}')
    if not status:
        sys.exit(1)

    pherc = prompt('Enter PHerc number: ')

    records = db.list_cornici_pezzi(pherc)
    if len(records) == 0 or (
            len(records) == 1 and
            records[0]['cr'] is None and
            records[0]['pz'] is None):
        print('No trays found.')
        sys.exit(1)

    print(f'Found {len(records)} items: ')
    records = sorted(records, key=record_sort)
    pad = 3
    for i, e in enumerate(records):
        print(f'{i + 1: {pad}}) {record_name(e)}')


if __name__ == '__main__':
    main()
