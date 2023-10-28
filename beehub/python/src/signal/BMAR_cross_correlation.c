#!/usr/bin/env C
# -*- coding: utf-8 -*-

#include <Python.h>
#include <stdio.h>

// Function to compute the cross-correlation
static PyObject* cross_correlate(PyObject* self, PyObject* args) {
    PyListObject* signal1;
    PyListObject* signal2;
    if (!PyArg_ParseTuple(args, "O!O!", &PyList_Type, &signal1, &PyList_Type, &signal2)) {
        return NULL;
    }

    Py_ssize_t n1 = PyList_Size((PyObject*)signal1);
    Py_ssize_t n2 = PyList_Size((PyObject*)signal2);
    Py_ssize_t n = n1 + n2 - 1; // Size of the output array

    PyObject* result_list = PyList_New(n);
    if (!result_list) {
        return NULL;
    }

    for (Py_ssize_t lag = 0; lag < n; lag++) {
        double sum = 0.0;
        Py_ssize_t k = lag - n2 + 1;
        if (k < 0) k = 0;
        for (; k < n1 && (lag - k) >= 0; k++) {
            PyObject* item1 = PyList_GetItem((PyObject*)signal1, k);
            PyObject* item2 = PyList_GetItem((PyObject*)signal2, lag - k);

            if (!item1 || !item2) {
                Py_DECREF(result_list);
                return NULL;
            }

            double val1 = PyFloat_AsDouble(item1);
            double val2 = PyFloat_AsDouble(item2);
            sum += val1 * val2;
        }
        PyObject* sum_obj = PyFloat_FromDouble(sum);
        if (!sum_obj) {
            Py_DECREF(result_list);
            return NULL;
        }
        PyList_SetItem(result_list, lag, sum_obj);  // Reference to sum_obj stolen
    }

    return result_list;
}

// Method table for the module
static PyMethodDef CrossCorrMethods[] = {
    {"cross_correlate", cross_correlate, METH_VARARGS, "Compute the cross-correlation of two sequences."},
    {NULL, NULL, 0, NULL}
};

// Module definition
static struct PyModuleDef crosscorrelationmodule = {
    PyModuleDef_HEAD_INIT,
    "cross_correlation",   // name of module
    NULL, // module documentation, may be NULL
    -1,       // size of per-interpreter state of the module, or -1 if the module keeps state in global variables.
    CrossCorrMethods
};

// Module initialization function
PyMODINIT_FUNC PyInit_cross_correlation(void) {
    return PyModule_Create(&crosscorrelationmodule);
}

/*
INSTRUCTIONS FOR COMPILING AND ADDING TO PYTHON:

Compile the C code: Save the code to a file, e.g., cross_correlation.c. 
Then compile the C code into a shared library that Python can import. 
You need to have Python development headers installed 
(usually package python3-dev or python3-devel).

compile with:

gcc -shared -fPIC -I /usr/include/python3.<n> -o cross_correlation.so cross_correlation.c

Use the C Function in Python: Once you have the shared library, 
you can use this function in your Python script like any other Python module.

import cross_correlation

signal1 = [1.0, 2.0, 3.0, 4.0]
signal2 = [0.0, 1.0, 0.5]

result = cross_correlation.cross_correlate(signal1, signal2)
print(result)

*/