from neo4j import GraphDatabase
import config

class HelloWorldExample:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def print_greeting(self, message):
        with self.driver.session() as session:
            greeting = session.execute_write(self._create_and_return_greeting, message)
            print(greeting)

    @staticmethod
    def _create_and_return_greeting(tx, message):
        result = tx.run("CREATE (a:Greeting) "
                        "SET a.message = $message "
                        "RETURN a.message + ', from node ' + id(a)", message=message)
        return result.single()[0]


if __name__ == "__main__":


    greeter = HelloWorldExample("neo4j://localhost:7687", config.username, config.password)
    
    #greeter = HelloWorldExample("neo4j://localhost:7687", username, password)
    #greeter = HelloWorldExample("neo4j://localhost:7687", config.username, config.password)
    greeter.print_greeting("hello, world")
    greeter.close()
