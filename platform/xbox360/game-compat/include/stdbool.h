#ifndef SMASH360_C_STDBOOL_H
#define SMASH360_C_STDBOOL_H
/* Standard C99 spellings. The generated semantic pass must lower _Bool for
 * the XDK C frontend; a missing pass fails compilation rather than silently
 * changing boolean conversion or object representation. C++ uses keywords. */
#ifndef __cplusplus
#define bool _Bool
#define true 1
#define false 0
#endif
#define __bool_true_false_are_defined 1
#endif
