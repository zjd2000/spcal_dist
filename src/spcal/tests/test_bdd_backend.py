#!/usr/bin/env python3
"""
Test script for CUDD acceleration in dd library
"""

import sys
import time


def test_cudd_acceleration():
    """Test if CUDD is working and measure performance"""
    try:
        import dd.cudd as _cudd

        print("✓ Successfully imported dd.cudd")
        cudd_available = True
    except ImportError as e:
        print(f"✗ Failed to import dd.cudd: {e}")
        cudd_available = False

    try:
        import dd.autoref as _autoref

        print("✓ Successfully imported dd.autoref")
        autoref_available = True
    except ImportError as e:
        print(f"✗ Failed to import dd.autoref: {e}")
        autoref_available = False

    if not cudd_available and not autoref_available:
        print("No dd backend available!")
        return False

    # Test basic functionality
    print("\n" + "=" * 50)
    print("Testing BDD operations...")
    print("=" * 50)

    if cudd_available:
        print("\n--- Testing with CUDD backend ---")
        test_bdd_operations(_cudd)

    if autoref_available:
        print("\n--- Testing with autoref backend ---")
        test_bdd_operations(_autoref)

    return True


def test_bdd_operations(backend):
    """Test BDD operations with given backend"""
    try:
        # Create BDD manager
        bdd = backend.BDD()

        # Declare variables
        variables = ["x", "y", "z"]
        for var in variables:
            bdd.declare(var)

        # Create some expressions
        start_time = time.time()

        # x AND y
        expr1 = bdd.add_expr("x & y")

        # y OR z
        expr2 = bdd.add_expr("y | z")

        # x XOR z
        expr3 = bdd.add_expr("x ^ z")

        # Complex expression: (x & y) | (y & z)
        expr4 = bdd.add_expr("(x & y) | (y & z)")

        # Count number of nodes
        node_count = bdd.count_nodes([expr1, expr2, expr3, expr4])

        # Perform operations
        result_and = bdd.apply("and", expr1, expr2)
        result_or = bdd.apply("or", expr3, expr4)

        end_time = time.time()

        print(f"✓ Successfully created {len(variables)} variables")
        print(f"✓ Created 4 BDD expressions")
        print(f"✓ Total nodes: {node_count}")
        print(f"✓ Operations completed in {end_time - start_time:.6f} seconds")
        print(f"✓ BDD manager info: {bdd.statistics()}")

        # Test evaluation
        model = {"x": True, "y": False, "z": True}
        eval_result = bdd.let(model, expr1)
        print(
            f"✓ Evaluation test: x=True, y=False, z=True -> expr1(x&y) = {eval_result}"
        )

        return True

    except Exception as e:
        print(f"✗ Error during BDD operations: {e}")
        return False


def performance_comparison():
    """Compare performance between backends if both are available"""
    try:
        import dd.autoref as autoref_backend
        import dd.cudd as cudd_backend

        print("\n" + "=" * 50)
        print("Performance Comparison")
        print("=" * 50)

        # Test with CUDD
        cudd_time = test_performance(cudd_backend, "CUDD")

        # Test with autoref
        autoref_time = test_performance(autoref_backend, "autoref")

        if cudd_time > 0 and autoref_time > 0:
            speedup = autoref_time / cudd_time
            print(f"\n🎯 Performance Results:")
            print(f"  CUDD:    {cudd_time:.6f} seconds")
            print(f"  autoref: {autoref_time:.6f} seconds")
            print(f"  Speedup: {speedup:.2f}x")

    except ImportError:
        print("Cannot perform comparison - both backends not available")


def test_performance(backend, name):
    """Test performance of a specific backend"""
    try:
        bdd = backend.BDD()

        # Create more variables for meaningful test
        n_vars = 10
        variables = [f"x{i}" for i in range(n_vars)]
        for var in variables:
            bdd.declare(var)

        start_time = time.time()

        # Create multiple expressions
        expressions = []
        for i in range(n_vars - 1):
            expr = bdd.add_expr(f"x{i} & x{i+1}")
            expressions.append(expr)

        # Perform multiple operations
        for i in range(len(expressions) - 1):
            result = bdd.apply("or", expressions[i], expressions[i + 1])

        end_time = time.time()

        print(f"✓ {name}: {end_time - start_time:.6f} seconds")
        return end_time - start_time

    except Exception as e:
        print(f"✗ {name} performance test failed: {e}")
        return -1


if __name__ == "__main__":
    print("CUDD Acceleration Test")
    print("=" * 30)

    success = test_cudd_acceleration()

    if success:
        performance_comparison()

    print("\n" + "=" * 50)
    print("Test completed!")
