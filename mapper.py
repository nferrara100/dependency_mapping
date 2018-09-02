import ast
import argparse
import os
import importlib
import networkx as nx
import statistics
from networkx.algorithms import approximation


class Search:

    def __init__(self):
        self.args = None
        self.tree = {}
        self.creator = {}
        self.py_files = []
        self.graph = {}
        self.logger = {}
        self.searched_files = set()
        self.searched_directories = set()
        self.crawled_imports = set()
        self.uncrawled = set()

        self.get_input()

    # Gets input data
    def get_input(self):
        # Configures the command-line interface.
        parser = argparse.ArgumentParser(
            description='Graph interfunctional Python dependencies. Searches given modules '
                        'and/or directories and lists included functions along with their '
                        'dependents.')
        parser.add_argument('filename', metavar='F', type=str, nargs="*",
                            help="the name(s) of files and directories to examine")
        parser.add_argument('--inverse', '-i', action='store_true', default=False,
                            help="inverse output so that dependencies are listed instead of dependents")
        parser.add_argument('--built-ins', '-b', action='store_true',
                            help="also graph when Python's built in functions are used")
        parser.add_argument('--raw', '-r', action='store_true', default=False,
                            help="remove instruction text and formatting")
        parser.add_argument('--connectivity', '-c', action='store_true', default=False,
                            help="print connectivity data")
        parser.add_argument('--no-refresh', '-n', action='store_true', default=False,
                            help="Exit after initial data print")
        args = parser.parse_args()

        # Processes the input parameters.
        if args.filename is None:
            args.filename[0] = input("Filename to examine: ")

        self.args = args


# Represents function nodes in the graph.
class FuncNode:

    def __init__(self, filename="", class_name="", name="", hidden=False, ast_node=None):
        self._filename = filename
        self._class_name = class_name
        self._name = name
        self._hidden = hidden

        # All of the other nodes this node calls.
        self._dependencies = set()
        # All the other nodes that call this node.
        self._dependents = set()
        self._ast_node = ast_node

    def __repr__(self):
        return self._filename + ":" + self._class_name + "." + self._name

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__ and
            self._filename == other.get_filename() and
            self._class_name == other.get_class() and
            self._name == other.get_name()
        )

    # This prevents creating multiple nodes at the same position in the graph.
    def __hash__(self):
        return hash((self._filename, self._class_name, self._name))

    def get_string(self):
        return self.get_filename() + self.get_class() + self.get_name()

    def get_filename(self):
        return self._filename

    def get_class(self):
        return self._class_name

    # Returns true if identifier might be used by the AST to identify the node.
    def is_identifier(self, identifier):
        if self._filename == identifier or self._class_name == identifier or self._filename == identifier:
            return True
        else:
            return False

    def get_name(self):
        return self._name

    def is_hidden(self):
        if self._hidden is True and len(self._dependencies) == 0 and len(self._dependents) == 0:
            return True
        else:
            return False

    def is_secondary(self):
        return self._hidden

    def add_dependency(self, dependency):
        self._dependencies.add(dependency)

    def add_dependent(self, dependent):
        self._dependents.add(dependent)

    def get_edges(self, inverse=False):
        if inverse is True:
            return self._dependencies
        else:
            return self._dependents

    # Returns a string of all the edges.
    def get_edges_str(self, inverse=False):
        return_str = ""
        for edge in sorted(self.get_edges(inverse), key=lambda the_node: the_node.get_string()):
            return_str += "(" + repr(edge) + ") "
        return return_str

    def get_ast_node(self):
        return self._ast_node

    def get_indegree(self):
        return len(self._dependents)

    def get_outdegree(self):
        return len(self._dependencies)


# Parent class for basic AST parsing. Meant to be extended depending on the task.
class ASTParser(ast.NodeVisitor):
    graph = {}

    def __init__(self, filename="", built_ins=False, recursive=False, imports=None):
        self.current_class = ""
        self.current_function = ""
        self.filename = filename
        self.allow_built_ins = built_ins
        if imports is None:
            self._imports = set()
        else:
            self._imports = imports
        self._uncrawled = set()

        # Removes file extension.
        # self.current_filename = self.filename[:-3]
        self.current_filename = self.filename
        # Removes directory for simplicity. Should be included in future versions.
        self.current_filename = self.current_filename.split(os.sep)[-1]
        self.directory = ""
        self.recursive = recursive
        if self.recursive is False:
            for x in self.filename.split(os.sep)[:-1]:
                self.directory += x + os.sep
            self.directory = self.directory.replace(os.getcwd() + os.sep, "")
        # self.full_directory = os.getcwd() + os.sep + self.directory

    def visit_ClassDef(self, node):
        self.handle_node(node, "current_class", self.generic_visit)

    def visit_FunctionDef(self, node):
        self.handle_node(node, "current_function", self.generic_visit)

    def handle_node(self, node, title, handler):
        old_title = self.__dict__[title]
        self.__dict__[title] = node.name
        handler(node)
        self.__dict__[title] = old_title

    # Returns the graph this instance created.
    def get_graph(self):
        return self.graph

    # Adds the given node to the graph if it is not already in it.
    def add_node(self, node):
        if node not in self.graph:
            self.graph[node] = node


# Searches AST for nodes and adds them to the graph.
class NodeCreator(ASTParser):

    def visit_Import(self, node):
        # print(ast.dump(node))
        if self.recursive is False:
            for reference in node.names:
                folders = self.directory.split(os.sep)
                self.crawl_import(node, reference, folders)

    def crawl_import(self, node, reference, folders, folder_index=0):
        try:
            folder = ""
            x = len(folders) - folder_index
            while x < len(folders) - 1:
                if folders[x] != "":
                    folder += folders[x] + "."
                x += 1
            imported_name = folder + reference.name
            # if imported_name not in self._imports:
            imported = importlib.import_module(imported_name)
            # relative_imported = imported.__file__.replace(os.getcwd() + os.sep, "")
            visitor = NodeCreator(imported.__file__, built_ins=True, recursive=True)
            tree_file = open(imported.__file__)
            tree = ast.parse(tree_file.read())
            self._imports.add(imported_name)
            visitor.visit(tree)
        except ImportError:
            if folder_index < len(folders):
                self.crawl_import(node, reference, folders, folder_index+1)
            else:
                self._uncrawled.add(reference.name)
        except AttributeError:
            self._uncrawled.add(reference.name)

    def get_uncrawled(self):
        return self._uncrawled

    def get_imports(self):
        return self._imports

    def visit_ClassDef(self, node):
        self.handle_node(node, "current_class", self.add_class_node)

    def add_class_node(self, node):
        current_node = FuncNode(filename=self.current_filename, class_name=self.current_class,
                                name="__init__", hidden=self.recursive)
        self.add_node(current_node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.handle_node(node, "current_function", self.add_function_node)

    # Creates a node for the function even though it might not be connected to any other nodes.
    def add_function_node(self, node):
        current_node = FuncNode(filename=self.current_filename, class_name=self.current_class,
                                name=self.current_function, hidden=self.recursive, ast_node=node)
        self.add_node(current_node)
        self.generic_visit(node)


# Detects connections in the AST and adds them as edges in the graph.
class EdgeDetector(ASTParser):

    # Records actual function calls
    def visit_Call(self, node):
        # print(ast.dump(node))

        # Checks for information to reconstruct the fully qualified name of the node. Not enough data is in the AST
        # to always be able to find the right node.
        if "value" in dir(node.func):
            dependency = node.func.attr
            try:
                home = node.func.value.id
            except AttributeError:
                home = self.current_class
        else:
            try:
                dependency = node.func.id
                home = self.current_filename
            except AttributeError:
                print("big error")
                self.generic_visit(node)
                return

        # Checks if the current call is to a built-in function.
        is_built_in = False
        if dependency in dir(__builtins__):  # sys.builtin_module_names
            is_built_in = True

        if is_built_in is False or self.allow_built_ins is True:
            dependency_node = None
            already_found = False
            # Searches the graph and selects the node being referenced.
            for n in self.graph:
                if n.get_name() == dependency or (n.get_name() == "__init__" and n.get_class() == dependency):
                    if already_found is True:
                        # If there is a conflict and this is a more exact match save this.
                        if n.is_identifier(home) is True and dependency_node.is_identifier(home) is False:
                            dependency_node = n
                        # Do nothing if existing node is better.
                        if n.is_identifier(home) is False and dependency_node.is_identifier(home) is True:
                            pass
                        # If neither or both match throw an error. This should not happen normally.
                        else:
                            pass
                            # print("Mapper could not definitively determine the instance of " + dependency +
                            #       " that was called by " + self.current_function)
                    else:
                        dependency_node = n
                    already_found = True

                if n.get_ast_node() == node:
                    this_node = n

            # Creates this node if it was not already in the graph.
            try:
                this_node
            except NameError:
                if self.current_function == "":
                    self.current_function = "__main__"

                this_node = FuncNode(filename=self.current_filename, class_name=self.current_class,
                                     name=self.current_function, ast_node=node)

            self.add_edge(is_built_in, dependency, this_node, dependency_node,)

        self.generic_visit(node)

    # Adds an edge to the graph.
    def add_edge(self, is_built_in, dependency, this_node, dependency_node=None,):
        # Error handling if the node's identity could not be determined.
        if dependency_node is None:
            if is_built_in is True:
                class_name = "Builtins"
                dependency_file = "System"
            else:
                class_name = "Unknown"
                dependency_file = "Unknown"
            dependency_node = FuncNode(filename=dependency_file, class_name=class_name, name=dependency)

        # Ensures that the relevant nodes are in the graph if they were not already.
        self.add_node(this_node)
        self.add_node(dependency_node)

        # This works even if the node was not added to the graph because the existing node's hash would be the same.
        self.graph[this_node].add_dependency(dependency_node)
        self.graph[dependency_node].add_dependent(this_node)


# Adds to the existing graph object.
def append_graph(found_filename, search):
    search.tree[found_filename] = ast.parse(open(found_filename).read())
    search.creator[found_filename] = NodeCreator(found_filename, imports=search.crawled_imports)
    search.creator[found_filename].visit(search.tree[found_filename])
    search.crawled_imports.union(search.creator[found_filename].get_imports())
    search.uncrawled.union(search.creator[found_filename].get_uncrawled())
    # print(" ".join(search.uncrawled))
    print("Len: " + repr(len(search.uncrawled)))
    search.py_files.append(found_filename)
    return {**search.graph, **search.creator[found_filename].get_graph()}


def get_nx_graph(graph):
    nxg = nx.DiGraph()
    for node in graph:
        nxg.add_node(node)
    for node in graph:
        for edge in node.get_edges():
            nxg.add_edge(node, edge)
    return nxg


# Prints the results including a list of functions and their dependencies in the terminal.
def output_text(search):
    indent = ""

    if search.args.raw is not True:
        searched_str = " ".join(search.searched_files) + " ".join(search.searched_directories)

        if searched_str != "":
            print("Mapper searched: %s" % searched_str)

            if len(search.crawled_imports) is not 0:
                imports_str = " ".join(sorted(search.crawled_imports))
                print("Mapper also crawled imports from: %s" % imports_str)

            if len(search.uncrawled) is not 0:
                uncrawled_str = " ".join(sorted(search.uncrawled))
                print("Mapper could not crawl the following imports: %s" % uncrawled_str)

            if search.args.connectivity is True:
                nxg = get_nx_graph(search.graph)
                degree_sequence = sorted([d for n, d in nxg.degree()], reverse=True)
                max_degree = max(degree_sequence)
                mean_degree = statistics.mean(degree_sequence)
                all_pairs_con = nx.algorithms.approximation.connectivity.all_pairs_node_connectivity(nxg)
                # Very slow
                # average_connectivity = nx.algorithms.connectivity.connectivity.average_node_connectivity(nxg)
                edge_connectivity = nx.algorithms.connectivity.connectivity.edge_connectivity(nxg)
                is_connected = nx.is_connected(nxg.to_undirected())
                node_num = nxg.number_of_nodes()
                maximal_independent_set = nx.algorithms.mis.maximal_independent_set(nxg.to_undirected())
                degree_centrality = nx.algorithms.centrality.degree_centrality(nxg)
                edge_load_centrality = nx.algorithms.centrality.edge_load_centrality(nxg)
                global_reaching_centrality = nx.algorithms.centrality.global_reaching_centrality(nxg)
                degree_histogram = nx.classes.function.degree_histogram(nxg)
                density = nx.classes.function.density(nxg)
                if is_connected:
                    minimum_edge_cut = nx.algorithms.connectivity.cuts.minimum_edge_cut(nxg)
                    print('Minimum edge cut: ' + repr(minimum_edge_cut))

                print('Average Degree: {0:.2f}'.format(mean_degree))
                print('Max Degree: ' + repr(max_degree))
                # print('Average Connectivity: {0:.2f}'.format(average_connectivity))
                print('Edge Connectivity: {0:.2f}'.format(edge_connectivity))
                print('Is connected: ' + repr(is_connected))
                print('Number of nodes: ' + repr(node_num))
                # print('Maximal independent set: ' + repr(maximal_independent_set))
                # print('Degree Centrality: ' + repr(degree_centrality))
                # print('Edge Load Centrality: ' + repr(edge_load_centrality))
                print('Global reaching centrality: ' + repr(global_reaching_centrality))
                print('Degree Histogram: ' + repr(degree_histogram))
                print('Density: ' + repr(density))

            if search.args.inverse is True:
                dependents_string = "Dependencies"
            else:
                dependents_string = "Dependents"
            indent = "-40"
            title_str = "\n%" + indent + "s %" + indent + "s\n"
            print(title_str % ("Function Name", dependents_string))

    # Prints each line of the data.
    format_string = "%" + indent + "s %" + indent + "s"
    for node in sorted(search.graph, key=lambda the_node: the_node.get_string()):
        if node.is_hidden() is False:
            print(format_string % (node, node.get_edges_str(inverse=search.args.inverse)))


# Main initial execution of the script via the command-line.
def main():
    search = Search()

    if search.args.filename is not None:
        for filename in search.args.filename:
            filename = os.path.abspath(os.path.expanduser(filename))
            if os.path.isdir(filename):
                search.searched_directories.add(filename + os.sep)
                for file in os.walk(filename, followlinks=True):
                    for i in range(len(file[2])):
                        found_filename = file[0] + os.sep + file[2][i]
                        if found_filename[-3:] == ".py":
                            search.graph = append_graph(found_filename, search)
            else:
                # Adds ".py" to the end of the file if that was not specified.
                if filename[-3:] != ".py":
                    filename += ".py"
                if os.path.isfile(filename):
                    search.searched_files.add(filename)
                    search.graph = append_graph(filename, search)
                else:
                    print("Error: Could not find %s" % filename)

    # Processes each file.
    for file in search.py_files:
        search.logger[file] = EdgeDetector(file, search.args.built_ins)
        search.logger[file].visit(search.tree[file])
        search.graph = {**search.graph, **search.logger[file].get_graph()}

    output_text(search)


# Calls the main function to start the script.
if __name__ == "__main__":
    main()
    print()
