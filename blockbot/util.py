'''
    util
    ====

    Utilities for blockbot.
'''


def chunks(sequence, step, start_index=0):
    '''
    Yield chunks of size `step` from sequence.

    :param sequence: Sequence to chunk into smaller subsequences.
    :param step: Chunk size.
    :param start_index: (Optional) Index to start from in sequence.
    '''

    for index in range(start_index, len(sequence), step):
        start_index = index
        end_index = start_index + step
        yield sequence[start_index:end_index]
