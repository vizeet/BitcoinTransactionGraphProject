from block_parser import getBlock
from leveldb_parser import getBlockIndex, getRecentBlockHash
import os
import mmap
import binascii
import json
from utility_adapters.graph_adapter import GraphAdapter
import argparse

host             = "localhost"
port             = 7687
user             = "neo4j"
password         = "test"

snap_bitcoin_path = os.path.join(os.getenv('HOME'), 'snap', 'bitcoin-core', 'common')
bitcoin_path = os.path.join(snap_bitcoin_path, '.bitcoin')
blocks_path = os.path.join(bitcoin_path, 'blocks')

graph_adapter = GraphAdapter(host=host, port=port, user=user, password=password)

def traverse_blockchain_in_reverse(block_count: int):
        global graph_adapter

        prev_block_hash_bigendian_b = getRecentBlockHash()
#        print('next block hash = %s' % bytes.decode(binascii.hexlify(next_block_hash_bigendian_b[::-1])))
        for _ in range(block_count):
                jsonobj = getBlockIndex(prev_block_hash_bigendian_b)
                if 'data_pos' in jsonobj:
                        block_filepath = os.path.join(blocks_path, 'blk%05d.dat' % jsonobj['n_file'])
                        start = jsonobj['data_pos']
                        print('height = %d' % jsonobj['height'])
                elif 'undo_pos' in jsonobj:
                        block_filepath = os.path.join(blocks_path, 'rev%05d.dat' % jsonobj['n_file'])
                        start = jsonobj['undo_pos']

                with open(block_filepath, 'rb') as block_file:
                        # load file to memory
                        mptr = mmap.mmap(block_file.fileno(), 0, prot=mmap.PROT_READ) #File is open read-only
                        prev_block_hash_bigendian_b, block = getBlock(mptr, start)

                graph_adapter.createTxnGraph(block)

                if jsonobj['height'] == 1:
                        break

if __name__ == '__main__':
        parser = argparse.ArgumentParser(description='Process Blocks in reverse to generate graph of given number of blocks')
        parser.add_argument("-c", "--block_count", type=int, default=5, help="Retrieve recent number of blocks. Default: 5")

        args = parser.parse_args()

        print('block_count = %d' % args.block_count)

        traverse_blockchain_in_reverse(args.block_count)
