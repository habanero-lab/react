import sys
import ast
import inspect
import textwrap
import ast_transforms
from ast_transforms import apply_transform_on_ast
from .transforms import attach_index_notation, op_to_loop, trie_fuse, insert_allocations, parallelize
from .transforms import assign_sparse_to_dense, sparsify_loops

def Index(*args):
    pass

def compile(fn):
    newsrc = compile_from_src(inspect.getsource(fn), trie_fuse=1)
    header = textwrap.dedent('''
    import numba
    from numpy import empty, zeros
    ''')
    newsrc = header + newsrc
    m = ast_transforms.utils.load_code(newsrc)
    return getattr(m, fn.__name__)

def compile_from_src(src, **options):
    tree = ast.parse(src)
    tree = apply_transform_on_ast(tree, "remove_func_decorator")
    tree = apply_transform_on_ast(tree, "to_single_op_form")
    tree = assign_sparse_to_dense.transform(tree)
    tree = apply_transform_on_ast(tree, "attach_def_use_vars")
    tree = attach_index_notation.transform(tree)
    tree = insert_allocations.transform(tree)
    tree = op_to_loop.transform(tree)
    tree = sparsify_loops.transform(tree)
    if options.get("trie_fuse", False):
        tree = trie_fuse.transform(tree)
    if options.get("use_numba", False):
        if options.get("parallelize", False):
            tree = parallelize.transform(tree)
            tree = apply_transform_on_ast(tree, "add_func_decorator", "numba.njit(parallel=True)")
        else:
            tree = apply_transform_on_ast(tree, "add_func_decorator", "numba.njit")
    tree = apply_transform_on_ast(tree, "remove_func_arg_annotation")
    tree = apply_transform_on_ast(tree, "where_to_ternary")
    return ast_to_code(tree)

def ast_to_code(tree):
    return ast.unparse(tree).replace('# type:', '#')
