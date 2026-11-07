#pragma once
#include <stddef.h>
// The ImVector iterator API and ordinary C arrays; no ownership changes.
template <class T> inline typename T::iterator Smash360ImGuiBegin(T& value) { return value.begin(); }
template <class T> inline typename T::iterator Smash360ImGuiEnd(T& value) { return value.end(); }
template <class T> inline typename T::const_iterator Smash360ImGuiBegin(const T& value) { return value.begin(); }
template <class T> inline typename T::const_iterator Smash360ImGuiEnd(const T& value) { return value.end(); }
template <class T, size_t N> inline T* Smash360ImGuiBegin(T (&value)[N]) { return value; }
template <class T, size_t N> inline T* Smash360ImGuiEnd(T (&value)[N]) { return value + N; }
