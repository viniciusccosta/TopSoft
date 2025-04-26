def process_batch(batch):
    return [line.strip().split() for line in batch]


def read_in_batches(filename, batch_size=1000):
    with open(filename, "r") as f:
        batch = []
        for line in f:
            batch.append(line)
            if len(batch) == batch_size:
                yield process_batch(batch)
                batch = []
        if batch:
            yield process_batch(batch)  # process the last batch
