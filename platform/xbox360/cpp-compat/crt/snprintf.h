#ifndef SMASH360_CRT_SNPRINTF_H
#define SMASH360_CRT_SNPRINTF_H
#include "sources/crt/format.h"

#define Smash360_Vsnprintf Shipyard_Vsnprintf
#ifdef SMASH360_CRT_HOST_TEST
#define Smash360_snprintf shipyard_snprintf
#endif
#endif
