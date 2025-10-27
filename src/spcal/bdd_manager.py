#!/usr/bin/env python3
"""
Unified BDD Interface - Automatically selects the best backend, transparent to upper-level code
"""

import importlib
import os

from spcal.utils.logger import logger


class BDDManager:
    """
    Unified BDD manager that automatically selects the best available backend
    """

    # Backend priority (from highest to lowest)
    BACKEND_PRIORITY = ["cudd", "sylvan", "autoref"]

    def __init__(self, backend=None, **kwargs):
        """
        Initialize BDD manager

        Args:
            backend: Specify backend ('cudd', 'sylvan', 'autoref'), None for auto-selection
            **kwargs: Arguments passed to backend BDD constructor
        """
        self._backend_name = backend
        self._bdd_module = None
        self._bdd_instance = None
        self._kwargs = kwargs

        self._init_backend()

    def _init_backend(self):
        """Initialize backend"""
        if self._backend_name and self._backend_name in self.BACKEND_PRIORITY:
            # Use specified backend
            self._bdd_module = self._load_backend(self._backend_name)
            logger.info(f"Using specified backend: {self._backend_name}")
            if self._bdd_module is None:
                available = self.get_available_backends()
                logger.warning(
                    f"Specified backend '{self._backend_name}' is not available. "
                    f"Available backends: {available}"
                )
                if available:
                    self._backend_name = available[0]
                    self._bdd_module = self._load_backend(self._backend_name)
                else:
                    raise ImportError(
                        "No available BDD backend found. Please install dd package: pip install dd"
                    )
        else:
            # Automatically select the best backend
            self._bdd_module = self._auto_select_backend()
            logger.info(
                f"Auto-selected backend: {self._get_backend_name(self._bdd_module)}"
            )
            if self._bdd_module is None:
                raise ImportError(
                    "No BDD backend available. Please install dd package: pip install dd"
                )

        # Create BDD instance
        self._bdd_instance = self._bdd_module.BDD(**self._kwargs)

        # Print backend information (optional)
        if os.getenv("BDD_VERBOSE", "0") == "1":
            print(f"Using BDD backend: {self._get_backend_name(self._bdd_module)}")

    def _load_backend(self, backend_name):
        """Load specified backend"""
        try:
            module = importlib.import_module(f"dd.{backend_name}")
            # Simple test to verify it works
            test_bdd = module.BDD()
            test_bdd.declare("_test_var")
            _ = test_bdd.add_expr("_test_var")
            return module
        except (ImportError, AttributeError, Exception) as e:
            if os.getenv("BDD_DEBUG", "0") == "1":
                print(f"Backend {backend_name} failed to load: {e}")
            return None

    def _auto_select_backend(self):
        """Automatically select the best available backend"""
        for backend_name in self.BACKEND_PRIORITY:
            module = self._load_backend(backend_name)
            if module is not None:
                if os.getenv("BDD_VERBOSE", "0") == "1":
                    print(f"Auto-selected backend: {backend_name}")
                return module
        return None

    def _get_backend_name(self, module):
        """Get backend name"""
        if hasattr(module, "__name__"):
            return module.__name__.split(".")[-1]
        return "unknown"

    @classmethod
    def get_available_backends(cls):
        """Get all available backends"""
        available = []
        for backend_name in cls.BACKEND_PRIORITY:
            try:
                module = importlib.import_module(f"dd.{backend_name}")
                # Simple test
                test_bdd = module.BDD()
                test_bdd.declare("_test_var")
                _ = test_bdd.add_expr("_test_var")
                available.append(backend_name)
            except (ImportError, AttributeError, Exception):
                continue
        return available

    @classmethod
    def print_backend_info(cls):
        """Print backend information"""
        available = cls.get_available_backends()
        print("BDD Backend Information:")
        print(f"  Available backends: {available}")
        print(f"  Priority order: {cls.BACKEND_PRIORITY}")
        print(f"  Current auto-selection: {available[0] if available else 'None'}")

    def __getattr__(self, name):
        """Forward all undefined attribute calls to the underlying BDD instance"""
        if self._bdd_instance is None:
            raise RuntimeError("BDD instance not properly initialized")

        if hasattr(self._bdd_instance, name):
            return getattr(self._bdd_instance, name)
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

    def __dir__(self):
        """Combine BDD instance attributes with current class attributes"""
        base_attrs = set(super().__dir__())
        if self._bdd_instance is not None:
            bdd_attrs = set(dir(self._bdd_instance))
            base_attrs.update(bdd_attrs)
        return list(base_attrs)

    @property
    def backend_name(self):
        """Get the name of the currently used backend"""
        if self._bdd_module:
            return self._get_backend_name(self._bdd_module)
        return None


# Create convenient alias
BDD = BDDManager
