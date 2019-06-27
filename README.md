# BitcoinTransactionGraphProject
Transaction Graphs created using Neo4J for Bitcoin Blockchain using txindex and blockfiles 

## Requirements
1. python 3.6
2. python pip package manager
3. bitcoin-core 0.17 is installed
4. neo4j:3.5.6
5. Individual pip packages are in requirements.txt

## Installation
1. Please refer to installation of neo4j
2. run: pip install -r requirements.txt in your shell

## Execution
```
usage: traverse_block_indexes.py [-h] [-c BLOCK_COUNT]

Process Blocks in reverse to generate graph of given number of blocks

optional arguments:
  -h, --help            show this help message and exit
  -c BLOCK_COUNT, --block_count BLOCK_COUNT
                        Retrieve recent number of blocks. Default: 5
```
