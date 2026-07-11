## PIP Layering Context

PIP's layering is Controllers → Services (`IXxxService`) → QueryProviders (`IXxxQueryProvider`) → EF Entities. Judge SOLID adherence and class cohesion within this layering — flagging violations *of* the layering itself (e.g. a controller reaching past its service into a QueryProvider) is the Architecture & Patterns dimension's job, not this one.
