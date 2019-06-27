from py2neo import Graph
from py2neo.data import Node, Relationship
import json

#neo4j
#uri             = "bolt://localhost:7687"
#user            = "neo4j"
#password        = "test"

class GraphAdapter:
        def __init__(self, host, port, user, password):
                uri = 'bolt://%s:%d' % (host, port)
                self.graph = Graph(uri, auth=(user, password))

                self.graph.run("CREATE CONSTRAINT ON (tx:Txn) ASSERT tx.txid IS UNIQUE")
                self.graph.run("CREATE CONSTRAINT ON (a:Address) ASSERT a.address IS UNIQUE")

        def createTxnGraph(self, jsonobj: dict):
                query = """
                WITH {json} AS data
                UNWIND data.block as block
                CREATE (tx:Txn {txid:block.txn_hash}) 
                WITH tx, block
                UNWIND block.out as outs
                CREATE (o:Out {index:outs.index, txid:block.txn_hash, amount:outs.btc, script:outs.scriptpubkey}), (tx)-[:OUT]->(o)
                WITH o, outs
                UNWIND outs.address as address
                MERGE (a:Address {address:address})
                CREATE (o)-[:GOES_TO]->(a)
                """

                self.graph.run(query, json=jsonobj)

                self.graph.run("CREATE INDEX ON :Out(index, txid)")

                query = """
                WITH {json} AS data
                UNWIND data.block as block
                MATCH (tx:Txn {txid:block.txn_hash})
                UNWIND block.input as inner
                MATCH (po:Out) WHERE po.index=inner.prev_txn_out_index AND po.txid=inner.prev_txn_hash CREATE (po)-[:INPUT]->(tx)
                """

                self.graph.run(query, json=jsonobj)
