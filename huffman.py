import json

BLOCK = 4096

def generate_tree(path: str) -> list[(int, int)]:
    frequencies = [0] * 256
    # Having zero frequency for unused bytes means that the tree still contains them
    # And so can be used on any data
    with open(path, 'rb') as file:
        data = True
        while data:
            data = file.read(BLOCK)
            for byte in data:
                frequencies[byte] += 1
    tree = list()
    for (byte, frequency) in enumerate(frequencies):
        tree.append((frequency, [(0, 0, byte)]))
    while len(tree) >= 2:
        tree.sort(reverse=True)
        (first, second) = (tree.pop(), tree.pop())
        total_frequency = first[0] + second[0]
        # Add 1 bit at the front of left node, and 0 to at the front of right node
        next_node = [(code + (1 << bit_count), bit_count, byte) for (code, bit_count, byte) in first[1]] + second[1]
        next_node = [(code, bit_count + 1, byte) for (code, bit_count, byte) in next_node]
        tree.append((total_frequency, next_node))
    encoder_tree = [None] * 256
    for (code, bit_count, byte) in tree[0][1]:
        encoder_tree[byte] = (code, bit_count)
    return encoder_tree

def compress(input_path: str, output_path: str, encoder_tree: list[(int, int)]):
    buffer = []
    current_buffer_size = 0
    with open(input_path, 'rb') as input_file:
        with open(output_path, 'wb') as output_file:
            tree_text = json.dumps(encoder_tree).replace(' ', '') # Remove unneeded whitespace from the JSON representation of the tree
            output_file.write(tree_text.encode() + b'\0') # Add null byte at the end of tree to seperate it from following data
            next_bits = 0
            next = 0

            data = True
            while data:
                data = input_file.read(BLOCK)
                for byte in data:
                    (byte, bit_count) = encoder_tree[byte]
                    next_bits += bit_count
                    next <<= bit_count
                    next += byte
                    while next_bits >= 8:
                        next_bits -= 8;
                        selected_bits = next >> next_bits # Since next_bits has been reduced by 8, gets the front byte
                        buffer.append(selected_bits)
                        current_buffer_size += 1
                        if current_buffer_size > BLOCK: # Using counter is faster than using len
                            output_file.write(bytes(buffer))
                            buffer = []
                            current_buffer_size = 0
                        next -= selected_bits << next_bits # Remove byte from remaining bits
            if next_bits != 0:
                bits_left = 8 - next_bits
                next <<= bits_left
                decoder_tree = dict(((code, bit_count), byte) for (byte, (code, bit_count)) in enumerate(encoder_tree))
                # Find an invalid bit pattern, so that no extra characters get appended to the end
                for i in range(1 << bits_left):
                    valid = True
                    for x in range(bits_left + 1):
                        if (i >> (bits_left - x), x) in decoder_tree: # Bits are a valid bit pattern, so dicard option
                            valid = False
                            break
                    if valid:
                        next += i
                        break
                buffer.append(next)
                current_buffer_size += 1
            output_file.write(bytes(buffer))


def decompress(input_path: str, output_path: str):
    buffer = []
    current_buffer_size = 0
    with open(input_path, 'rb') as input_file:
        with open(output_path, 'wb') as output_file:
            data = input_file.read(BLOCK)
            while b'\0' not in data: # Read until has entire tree
                data += input_file.read(BLOCK)
            (text_tree, data) = data.split(b'\0', maxsplit=1)
            tree = json.loads(text_tree)
            decoder_tree = dict(((code, bit_count), byte) for (byte, (code, bit_count)) in enumerate(tree))

            next_bits = 0
            next = 0
            if not data:
                data = True
            while data:
                for byte in data:
                    next_bits += 8
                    next <<= 8
                    next += byte
                    found = True
                    while found:
                        found = False
                        for bit_count in range(1, next_bits + 1):
                            try:
                                shift = next_bits - bit_count
                                selected_bits = next >> shift
                                decoded = decoder_tree[(selected_bits, bit_count)]
                                next_bits -= bit_count
                                buffer.append(decoded)
                                current_buffer_size += 1
                                if current_buffer_size > BLOCK:
                                    output_file.write(bytes(buffer))
                                    buffer = []
                                    current_buffer_size = 0
                                next -= selected_bits << shift
                                found = True
                                break
                            except KeyError:
                                pass
                data = input_file.read(BLOCK)
            output_file.write(bytes(buffer))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mode')
    parser.add_argument('input_file')
    parser.add_argument('output_file')
    parser.add_argument('-t', '--use-tree', help='compress with given tree instead of generating new')
    args = parser.parse_args()
    if args.mode == 'build_tree':
        tree = generate_tree(args.input_file)
        with open(args.output_file, 'w') as file:
            json.dump(tree, file)
    elif args.mode == 'compress':
        if args.use_tree is not None:
            with open(args.use_tree) as file:
                tree = json.load(file)
        else:
            tree = generate_tree(args.input_file)
        compress(args.input_file, args.output_file, tree)
    elif args.mode == 'decompress':
        decompress(args.input_file, args.output_file)
    else:
        print('Invalid mode: %s, mode should be either build_tree, compress or decompress' % args.mode)

if __name__ == '__main__':
    main()
