import os
import glob
import binascii
import datetime
import shutil
import mmap
import hashlib
import json
import gc
import logging
import datetime
import sys
import pubkey_address

logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)

start_time = str(datetime.datetime.now())

logging.debug(start_time)

snap_bitcoin_path = os.path.join(os.getenv('HOME'), 'snap', 'bitcoin-core', 'common')
bitcoin_path = os.path.join(snap_bitcoin_path, '.bitcoin')
blocks_path = os.path.join(bitcoin_path, 'blocks')

def getCount(count_bytes):
        txn_size = int(binascii.hexlify(count_bytes[0:1]), 16)

        if txn_size < 0xfd:
                return txn_size
        elif txn_size == 0xfd:
                txn_size = int(binascii.hexlify(count_bytes[1:3][::-1]), 16)
                return txn_size
        elif txn_size == 0xfe:
                txn_size = int(binascii.hexlify(count_bytes[1:5][::-1]), 16)
                return txn_size
        else:
                txn_size = int(binascii.hexlify(count_bytes[1:9][::-1]), 16)
                return txn_size

def getCountBytes(mptr: mmap):
        mptr_read = mptr.read(1)
        count_bytes = mptr_read
        txn_size = int(binascii.hexlify(mptr_read), 16)

        if txn_size < 0xfd:
                return count_bytes
        elif txn_size == 0xfd:
                mptr_read = mptr.read(2)
                count_bytes += mptr_read
                txn_size = int(binascii.hexlify(mptr_read[::-1]), 16)
                return count_bytes
        elif txn_size == 0xfe:
                mptr_read = mptr.read(4)
                count_bytes += mptr_read
                txn_size = int(binascii.hexlify(mptr_read[::-1]), 16)
                return count_bytes
        else:
                mptr_read = mptr.read(8)
                count_bytes += mptr_read
                txn_size = int(binascii.hexlify(mptr_read[::-1]), 16)
                return count_bytes

g_genesis_flag = True
g_txn_index = 0
g_block_header_hash = ''
g_block_index = 0

def getTxnHash(txn: bytes):
        txn_hash = hashlib.sha256(hashlib.sha256(txn).digest()).digest()
        return bytes.decode(binascii.hexlify(txn_hash[::-1]))

def getPrevBlockHeaderHash(mptr: mmap, start: int):
        seek = start + 4 ## ignore block version
        mptr.seek(seek)
        prev_block_hash = mptr.read(32)
        return prev_block_hash

def getTransactionCount(mptr: mmap):
        count_bytes = getCountBytes(mptr)
        txn_count = getCount(count_bytes)
        return txn_count

def getCoinbaseTransaction(mptr: mmap):
        global g_txn_index, g_block_header_hash, g_block_index, g_genesis_flag
        txn = {}
        mptr_read = mptr.read(4)
        raw_txn = mptr_read
        mptr_read = getCountBytes(mptr)
        input_count = getCount(mptr_read)
        is_segwit = False
        if input_count == 0:
                # post segwit
                is_segwit = bool(int(binascii.hexlify(mptr.read(1)), 16))
                mptr_read = getCountBytes(mptr)
                input_count = getCount(mptr_read)
        raw_txn += mptr_read
        txn['input'] = []
        for index in range(input_count):
                txn_input = {}
                mptr_read = mptr.read(32)
                raw_txn += mptr_read
                mptr_read = mptr.read(4)
                raw_txn += mptr_read
                mptr_read = getCountBytes(mptr)
                raw_txn += mptr_read
                coinbase_data_size = getCount(mptr_read)
                fptr1 = mptr.tell()
                mptr_read = getCountBytes(mptr)
                raw_txn += mptr_read
                coinbase_data_bytes_in_height = getCount(mptr_read)
                mptr_read = mptr.read(coinbase_data_bytes_in_height)
                raw_txn += mptr_read
                fptr2 = mptr.tell()
                arbitrary_data_size = coinbase_data_size - (fptr2 - fptr1)
                mptr_read = mptr.read(arbitrary_data_size)
                raw_txn += mptr_read
                mptr_read = mptr.read(4)
                raw_txn += mptr_read

        mptr_read = getCountBytes(mptr)
        raw_txn += mptr_read
        out_count = getCount(mptr_read)
        txn['out'] = []
        for index in range(out_count):
                txn_out = {}
                txn_out['index'] = index
                mptr_read = mptr.read(8)
                raw_txn += mptr_read
                txn_out['btc'] = round(int(binascii.hexlify(mptr_read[::-1]), 16)/10**8, 8)
                mptr_read = getCountBytes(mptr)
                raw_txn += mptr_read
                scriptpubkey_size = getCount(mptr_read)
                mptr_read = mptr.read(scriptpubkey_size)
                raw_txn += mptr_read
                script_type = getScriptType(mptr_read)
                if script_type == "P2PKH":
                        txn_out['address'] = getAddressFromP2PKH(mptr_read)
                elif script_type == "P2SH":
                        txn_out['address'] = getAddressFromP2SH(mptr_read)
                elif script_type == "P2WPKH":
                        txn_out['address'] = getAddressFromP2WPKH(mptr_read)
                elif script_type == "P2WSH":
                        txn_out['address'] = getAddressFromP2WSH(mptr_read)
                txn_out['scriptpubkey'] = bytes.decode(binascii.hexlify(mptr_read))
                if txn_out['btc'] != 0.0:
                        txn['out'].append(txn_out)
        if is_segwit == True:
                for index in range(input_count):
                        count_bytes = getCountBytes(mptr)
                        witness_count = getCount(count_bytes)
                        for inner_index in range(witness_count):
                                count_bytes = getCountBytes(mptr)
                                txn_witness_size = getCount(count_bytes)
                                txn_witness_witness = bytes.decode(binascii.hexlify(mptr.read(txn_witness_size)))
        mptr_read = mptr.read(4)
        raw_txn += mptr_read
        locktime = int(binascii.hexlify(mptr_read[::-1]), 16)
        txn['txn_hash'] = getTxnHash(raw_txn)

        logging.debug(json.dumps(txn, indent=4))

        return txn

def getScriptType(script_pub_key: bytes):
        if len(script_pub_key) == 25 and script_pub_key[:3] == bytes([0x76, 0xa9, 0x14]) and script_pub_key[-2:] == bytes([0x88, 0xac]):
                return "P2PKH"
        if len(script_pub_key) == 23 and script_pub_key[:2] == bytes([0xa9, 0x14]) and script_pub_key[-1:] == bytes([0x87]):
                return "P2SH"
        if len(script_pub_key) == 22 and script_pub_key[:2] == bytes([0x00, 0x14]):
                return "P2WPKH"
        if len(script_pub_key) == 34 and script_pub_key[:2] == bytes([0x00, 0x20]):
                return "P2WSH"
        return "Other"

def getAddressFromP2PKH(script: bytes):
        hash160 = script[3:23]
        address = pubkey_address.pkh2address(hash160, 'mainnet')
        return address

def getAddressFromP2SH(script: bytes):
        sh = script[2:22]
        address = pubkey_address.sh2address(sh, 'mainnet')
        return address

def getAddressFromP2WPKH(script: bytes):
        hash160 = script[2:22]
        address = pubkey_address.hash2address(hash160, 'mainnet', is_segwit=True, is_script=False)
        return address

def getAddressFromP2WSH(script: bytes):
        hash256 = script[2:34]
        address = pubkey_address.hash2address(hash256, 'mainnet', is_segwit=True, is_script=True)
        return address

def getTransaction(mptr: mmap):
        global g_txn_index, g_block_header_hash, g_block_index
        txn = {}
        mptr_read = mptr.read(4)
        raw_txn = mptr_read
        mptr_read = getCountBytes(mptr)
        input_count = getCount(mptr_read)
        is_segwit = False
        if input_count == 0:
                # post segwit
                is_segwit = bool(int(binascii.hexlify(mptr.read(1)), 16))
                mptr_read = getCountBytes(mptr)
                input_count = getCount(mptr_read)
        raw_txn += mptr_read

        txn['input'] = []
        for index in range(input_count):
                txn_input = {}
                mptr_read = mptr.read(32)
                raw_txn += mptr_read
                txn_input['prev_txn_hash'] = bytes.decode(binascii.hexlify(mptr_read[::-1]))
                mptr_read = mptr.read(4)
                raw_txn += mptr_read
                txn_input['prev_txn_out_index'] = int(binascii.hexlify(mptr_read[::-1]), 16)
                mptr_read = getCountBytes(mptr)
                raw_txn += mptr_read
                scriptsig_size = getCount(mptr_read)
                mptr_read = mptr.read(scriptsig_size)
                raw_txn += mptr_read
#                scriptsig = bytes.decode(binascii.hexlify(mptr_read))
                mptr_read = mptr.read(4)
                raw_txn += mptr_read
#                sequence = int(binascii.hexlify(mptr_read[::-1]), 16)
                txn['input'].append(txn_input)
        mptr_read = getCountBytes(mptr)
        raw_txn += mptr_read
        out_count = getCount(mptr_read)
        txn['out'] = []
        for index in range(out_count):
                txn_out = {}
                txn_out['index'] = index
                mptr_read = mptr.read(8)
                raw_txn += mptr_read
                txn_out['btc'] = round(int(binascii.hexlify(mptr_read[::-1]), 16)/10**8, 8)
                mptr_read = getCountBytes(mptr)
                raw_txn += mptr_read
                scriptpubkey_size = getCount(mptr_read)
                mptr_read = mptr.read(scriptpubkey_size)
                raw_txn += mptr_read
                script_type = getScriptType(mptr_read)
                if script_type == "P2PKH":
                        txn_out['address'] = getAddressFromP2PKH(mptr_read)
                elif script_type == "P2SH":
                        txn_out['address'] = getAddressFromP2SH(mptr_read)
                elif script_type == "P2WPKH":
                        txn_out['address'] = getAddressFromP2WPKH(mptr_read)
                elif script_type == "P2WSH":
                        txn_out['address'] = getAddressFromP2WSH(mptr_read)
                txn_out['scriptpubkey'] = bytes.decode(binascii.hexlify(mptr_read))
                txn['out'].append(txn_out)
        if is_segwit == True:
                for index in range(input_count):
                        mptr_read = getCountBytes(mptr)
                        witness_count = getCount(mptr_read)
                        for inner_index in range(witness_count):
                                mptr_read = getCountBytes(mptr)
                                txn_witness_size = getCount(mptr_read)
                                txn_witness_witness = bytes.decode(binascii.hexlify(mptr.read(txn_witness_size)))
        mptr_read = mptr.read(4)
        raw_txn += mptr_read
        locktime = int(binascii.hexlify(mptr_read[::-1]), 16)
        txn['txn_hash'] = getTxnHash(raw_txn)

        logging.debug(json.dumps(txn, indent=4))

        return txn

def getBlock(mptr: mmap, start: int):
        global g_txn_index
        prev_block_header_hash = getPrevBlockHeaderHash(mptr, start)

        start += 80
        mptr.seek(start) ## skip block header
        txn_count = getTransactionCount(mptr)
        print('transaction count = %d' % txn_count)
        logging.debug('transaction count = %d' % txn_count)

        txn_list = []
        txn_list.append(getCoinbaseTransaction(mptr))
        for index in range(1, txn_count):
                g_txn_index = index
                txn = getTransaction(mptr)
                txn_list.append(txn)

        block = {}
        block['block'] = txn_list

        g_genesis_flag = False
        return prev_block_header_hash, block

