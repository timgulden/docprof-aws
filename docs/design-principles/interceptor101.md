# Interceptor 101 - Stack-Based Pattern

**Note:** This document describes the **stack-based interceptor pattern** used for ingestion pipelines. For command execution, the system uses a **middleware-style pattern**. See `docs/architecture/interceptor-patterns.md` for a comparison of both patterns.

Interceptors are an important architectural pattern used in our projects. Some understanding of them is helpful to allow new team members to come up to speed. This document collects information which might have been passed on in person in the Before Times.

**Current Usage:** This stack-based pattern is used for the ingestion pipeline (`src/interceptors/ingestion_pipeline.py`). For most command execution, see the middleware-style pattern in `src/interceptors/common.py`.
• What is an interceptor?
An Interceptor is a data structure commonly found in functional programming
environments and occasionally elsewhere. It promotes a simple design and
lifecycle and is expressed in lightweight, reusable components. We use it for our
back end microservices.
Specifically, an interceptor is a data structure consisting of 0 to 3 functions:
- enter, which is called on the way *into* an interceptor stack
- leave, which is called on the way *out of* an interceptor stack
- error, which is called in case of an error
• Why are these functions so special?
They all have the same signature. They all take one parameter, a context, which
is a collection of key-value pairs. They also return a context.
Any given interceptor’s job is to look at the context it has been passed, modify it,
and return the modified version. It should be as simple as possible, usually
modifying one key. The concept of simplicity is central here. If an interceptor
does more than one thing, it will not pass code review.
More interceptors are always preferred to larger interceptors
Interceptors also should do no error handling except as required for side effecting
APIs.
• What is the error handling ban about?
Interceptors are not called in isolation. They are arranged in a stack. A stack is
an ordered list of interceptors. When a stack is executed, it is passed an initial
context. This context is then passed to the enter function of the first (left to right)
interceptor in the stack. It performs its function and returns a context, which is
then passed to the enter function of the next interceptor in the stack, if one exists.
If there is no next interceptor, then the leave function in the current interceptor is
called, followed by the leave function in the previous interceptor, if there is one.
When the final (leftmost) leave function has completed, the final context is
returned by the stack execute function.
For example, given a stack of interceptors like:
I1, I2, I3
The execute function will call I1.enter, I2.enter, and I3.enter, passing the output
context of one as the input context of the next. Next, detecting that there are no
more interceptors in the stack, it will call the leave functions in reverse order, i.e.
I3.leave, I2.leave, and I1.leave.
This flow is only interrupted if an enter or leave throws an error. In this case, the
stack executor catches it, puts the error in the ’error’ key of the context and calls
the error function of the current interceptor. The error function should look at the
context it has been passed, perform any useful cleaning up, delete the ’error’ key
from the context, and return it.
Note that if the ’error’ key is not cleared, the stack executor will call the error
function of any previous interceptors in the stack instead of the leave function.
While there are rare cases where calling error on the way out is the preferred
behavior, most of the time, calling the error function of the interceptor which
threw the exception is all that will be required.
If the stack executor is still on the way ’into’ the stack (meaning calling enter
functions), it will switch directions and start calling the leave functions as though
it had reached the end of the interceptor stack.
To follow the previous example, the execute function will call I1.enter, I2.enter
but copy to if I2.enter throws an error, it will be caught and a context containing
the error will be passed to I2.error, followed by I1.leave. Note that due to the
error, stack execution will never reach I3.
• Why do we use interceptors?
Because their properties match up well with the needs of microservice design. If
one needs to write a service to read messages from a queue (I1.enter), gather
some external resources based on the contents of the message (i2.enter),
perform some function (I3.enter), and clean up external resources afterwards
(I2.leave), each of those functional needs maps to a specific function in a specific
interceptor in the stack.
Further, because interceptors are first class objects, they can be reused without
resorting to an object hierarchy, factories, handlers, and all that baggage. They
are just a simple data structure.
• Nested Contexts
Our use of interceptors has one wrinkle: we nest message processing stacks.
That is, there are some resources we want to gather once, at service startup (i.e.
enter), and tear down at service exit (leave). This is the ’outer’, or ’service-level’
stack. The enter of the final interceptor in an ’outer’ stack itself executes an
’inner’, or ’message-processing’ stack to read messages from a work queue and
process them.
• One last thing
At the top of this document, we defined interceptors as zero to three functions.
When defining an interceptor, any, all or none of =enter, leave or error must be
provided. If the stack executor looks for a function and it was not provided, it
continues as though it was an empty function.