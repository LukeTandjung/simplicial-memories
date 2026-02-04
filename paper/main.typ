#import "@preview/charged-ieee:0.1.4": ieee
#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node
#import "@preview/cetz:0.3.2"
#import "@preview/pintorita:0.1.4": render

#show: ieee.with(
  title: [
    Memory has Many Faces: Simplicial
    Complexes as a Agent Memory Layer
  ],
  abstract: [
    This paper proposes simplicial complexes as a high-order representation of
    the agent memory layer.
  ],
  authors: (
    (
      name: "Luke Tandjung",
    ),
  ),
  index-terms: (
    "Agent Memory",
    "Simplicial Complexes",
    "Knowledge Graphs",
    "RAG",
  ),
  bibliography: bibliography("refs.bib"),
  figure-supplement: [Fig.],
)

= Introduction
Almost all current state of the art agent memory architectures make use of vector or graph data models for storing
chunked text extracted from conversation sessions. Architectures such as Supermemory combines semantic search on memories
linked to extracted text chunks with relational knowledge chains to map how memories evolve over time.

Neither of these data models are representationally complete.


What are some of the current competitive (SOTA) memory architectures out there?
"Hybrid memory architectures achieve strong results but at the cost of engineering
complexity and retrieval coordination. We investigate whether a single, mathematically
grounded representation—simplicial complexes—can consolidate these capabilities while
maintaining competitive performance."

On LongMemEval, RAG systems achieve 86% accuracy while
graph-based methods reach only 71% @emergence2025.

When three or more entities
co-occur meaningfully, such as multiple concepts in a
conversation, or events in a session, pairwise graphs
either discard this information @salnikov2018 or attempt
reconstruction through secondary inference @benson2018.
Even frameworks like SER fail to resolve it.
Recent attempts at formalising this information loss
include Wang and Kleinberg (2024), which proved the
combinatorial impossibility of recovering higher-order
structures from graph projections @wang2024.


= Motivation: A Category Theoretic Lens

/ Category.: A category $C$ consists of
- A collection of objects $a, b, c, ...$ denoted formally as
  the *class* $"ob"(C)$.
- A collection of *morphisms* (arrows) $"hom"_(C)(a, b)$ for
  each object pair $a, b$ in $"ob"(C)$. The expression $f:a -> b$
  indicates that $f$ is a morphism that maps $a$ to $b$, as
  depicted in the commutative diagram below. The collection of $"hom"_(C)(a, b)$ for all object pairs
  $a, b$ in $"ob"(C)$ is denoted as $"hom"(C)$.

  #align(center)[
    #diagram(
      cell-size: 15mm,
      $
        a edge(f, ->) & b
      $,
    )
  ]

- The composition binary operator $compose$; that is, for
  any three objects $a, b, c$ in $"ob"(C)$,

  $ compose: "hom"_(C)(a, b) times "hom"_(C)(b, c) -> "hom"_(C)(a, b) $

  That is, given morphisms $f:a -> b$ and $g: b -> c$, the
  morphisms $g compose f: a -> c$ exists, depicted below.

  #align(center)[
    #diagram(
      cell-size: 15mm,
      $
        a edge(->, f) edge("dr", ->, g compose f) & b edge("d", ->, g) \
                                                  & c
      $,
    )
  ]

  Furthermore, the composition operation satisfies *associativity*
  and *identity* rules.
  1. *Associativity*: For four objects $a, b, c, d$ in $"ob"(C)$
    and morphisms $f:a -> b$, $g:b -> c$, $h:c -> d$, we have

    $ ( h compose g) compose f = h compose (g compose f) $

  2. *Identity*: For every object $x$ in $"ob"(C)$, there
    exists an identity morphism $"id"_x:x -> x$ such that
    for every morphism $f:a -> b$, we have

    $ "id"_(b) compose f = f = f compose "id"_(a) $

Some examples of categories and their morphisms are sets
and functions, groups and group homeomorphisms, vector
spaces and linear maps, and topologies and continuous maps.

#pagebreak()

/ Functor.: A functor $F:C -> D$ is a *structure-preserving*
map between categories $C$ and $D$. In particular,
- it assigns each object $a$ in $"ob"(C)$ an object $F(a)$
  in $"ob"(D)$.
- it assigns each morphism $f:a -> b$ in $"hom"(C)$ a morphism
  $F(f):F(a) -> F(b)$ in $"hom"(D)$, such that $F("id"_(x))="id"_(F(x))$
  and $F(f compose g) = F(f) compose F(g)$.

With that in mind, we can view representations as categories:
vector embeddings as *Vect*, directed labelled graphs as *Vect*,
and simplicial complexes as *SC*. Mapping from simplicial complexes
to graphs happens via the *$1$-skeleton functor* $F$. Likewise,
mapping from simplicial complexes to vector spaces happens via
the *simplicial homology functor* $H_k$.

#align(center)[
  #diagram(
    cell-size: 15mm,
    $
      "SC" edge(->, F) edge("dr", ->, H_k) & "Graph" \
                                           & "Vect"
    $,
  )
]

However, as seen from the above diagram, no natural functor exists
from graphs back to simplicial complexes. Given three
mutually connected entities ${a, b, c}$, the graph doesn't indicate
whether these entities co-occurred together (a filled
triangle) or merely pairwise across contexts (an empty
triangle) as seen in @fig:graph-vs-simplex. This presents an implication for agent memory,
When users discuss multiple concepts together, these
co-occurrences carry semantic significance beyond
pairwise projections. Graph-based systems either discard
this at storage or attempt reconstruction at retrieval,
both degrading performance.

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Left: Graph (empty triangle)
    line((0, 0), (1.5, 0), stroke: black)
    line((1.5, 0), (0.75, 1.3), stroke: black)
    line((0.75, 1.3), (0, 0), stroke: black)
    circle((0, 0), radius: 0.1, fill: black)
    circle((1.5, 0), radius: 0.1, fill: black)
    circle((0.75, 1.3), radius: 0.1, fill: black)
    content((0, -0.3), $a$)
    content((1.5, -0.3), $b$)
    content((0.75, 1.6), $c$)
    content((0.75, -0.8), [Graph: edges only])

    // Right: Simplicial complex (filled triangle)
    line(
      (4, 0),
      (5.5, 0),
      (4.75, 1.3),
      close: true,
      fill: rgb("#cce5ff"),
      stroke: black,
    )
    circle((4, 0), radius: 0.1, fill: black)
    circle((5.5, 0), radius: 0.1, fill: black)
    circle((4.75, 1.3), radius: 0.1, fill: black)
    content((4, -0.3), $a$)
    content((5.5, -0.3), $b$)
    content((4.75, 1.6), $c$)
    content((4.75, -0.8), [Simplex: filled 2-simplex])
  }),
  caption: [A graph represents only pairwise edges, while a
    simplicial complex captures the 2-simplex ${a,b,c}$ as a
    filled face, encoding joint co-occurrence.],
) <fig:graph-vs-simplex>

Simplicial complexes avoid this by representing higher-order
co-occurences as first class objects. The functor hierarchy
establishes representational power: complexes project to
graphs and to embeddings, but systems at lower levels cannot
recover richer structure. This points towards how memory
systems should store information in the most structured
form and project to coarser representations only when
required.

#colbreak()

= Simplicial Complex for Knowledge
/ Simplicial Complex.: A simplicial complex (@fig:simplicial-complex) is a pair
$R=(V, S)$ where
- $V$ is the *vertex set* $V={v_1, v_2, ..., v_n}$
- $S$ is the *simplex/face set*. It is the set of non-empty subsets of
  $V$ that satisfies the following properties by construction:
  1. $v in V arrow.r.double {v} in S$
  2. $s_1 in S, s_2 subset.eq s_1 arrow.r.double s_2 in S$. Here, $s_2$ is called
    the *face* of the simplex $s_1$. Furthermore, if $s_2 subset s_1$,
    $s_2$ is called the *proper face* of the simplex $s_1$.

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Tetrahedron (3-simplex)
    let a = (0, 0)
    let b = (1.8, 0)
    let c = (0.9, 1.5)
    let d = (0.9, 0.55)

    line(a, b, c, close: true, fill: rgb("#e6f0ff"), stroke: black)
    line(a, b, d, close: true, fill: rgb("#99c2ff"), stroke: black)
    line(b, c, d, close: true, fill: rgb("#b3d1ff"), stroke: black)
    line(a, c, d, close: true, fill: rgb("#cce5ff"), stroke: black)

    // Additional 2-simplex sharing edge
    let e = (2.6, 1.4)
    line(b, c, e, close: true, fill: rgb("#d4edda"), stroke: black)

    // Another 2-simplex
    let f = (3.4, 0)
    line(b, e, f, close: true, fill: rgb("#fff3cd"), stroke: black)

    // 1-simplex (edge not part of a 2-face)
    let g = (4.2, 1.2)
    line(e, g, stroke: black)

    // Another edge
    let h = (4.4, 0.2)
    line(f, h, stroke: black)

    // Isolated 0-simplex
    let i = (5, 0.9)

    // Draw all vertices
    circle(a, radius: 0.08, fill: black)
    circle(b, radius: 0.08, fill: black)
    circle(c, radius: 0.08, fill: black)
    circle(d, radius: 0.08, fill: black)
    circle(e, radius: 0.08, fill: black)
    circle(f, radius: 0.08, fill: black)
    circle(g, radius: 0.08, fill: black)
    circle(h, radius: 0.08, fill: black)
    circle(i, radius: 0.08, fill: black)
  }),
  caption: [A simplicial complex containing a 3-simplex (blue tetrahedron),
    2-simplices (filled triangles), 1-simplices (edges), and 0-simplices
    (vertices). By downward closure, all faces of higher-dimensional
    simplices are automatically included.],
) <fig:simplicial-complex>

The second property of *downward closure* for simplicial
complexes distinguishes simplicial complexes from other possible
candidates of knowledge representation like hypergraphs. If
entities ${v_1, v_2, v_3}$ exists, then ${v_1, v_2}$, ${v_2, v_3}$,
${v_1, v_3}$, ${v_1}$, ${v_2}$, ${v_3}$ must exist. This captures
semantic intuition: joint co-occurrence implies all
sub-co-occurrences occurred. If three concepts were
discussed together, each pair was discussed, and each
individually. The way to describe such co-occurence
is baked into the structure of simplicial complexes. If
$s in S$ has $k+1$ elements, where $k >= 0$, $s$ is said to
be a *$k$-simplex* of dimension $k$. A point is a 0-simplex,
a line a 1-simplex, a filled triangle a 2-simplex, and a
tetrahedron a 3-simplex (@fig:simplex-dimensions).

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Top row
    // 0-simplex (point) - top left
    circle((0.75, 3.5), radius: 0.12, fill: black)
    content((0.75, 2.5), [0-simplex])

    // 1-simplex (edge) - top right
    line((4, 3), (5.2, 4), stroke: black)
    circle((4, 3), radius: 0.1, fill: black)
    circle((5.2, 4), radius: 0.1, fill: black)
    content((4.6, 2.5), [1-simplex])

    // Bottom row
    // 2-simplex (filled triangle) - bottom left
    line(
      (0, 0),
      (1.5, 0),
      (0.75, 1.2),
      close: true,
      fill: rgb("#cce5ff"),
      stroke: black,
    )
    circle((0, 0), radius: 0.1, fill: black)
    circle((1.5, 0), radius: 0.1, fill: black)
    circle((0.75, 1.2), radius: 0.1, fill: black)
    content((0.75, -0.5), [2-simplex])

    // 3-simplex (tetrahedron) - bottom right
    let p1 = (3.75, 0)
    let p2 = (5.25, 0)
    let p3 = (4.5, 1.2)
    let p4 = (4.5, 0.5)

    line(p1, p2, p3, close: true, fill: rgb("#e6f0ff"), stroke: black)
    line(p1, p2, p4, close: true, fill: rgb("#99c2ff"), stroke: black)
    line(p2, p3, p4, close: true, fill: rgb("#b3d1ff"), stroke: black)
    line(p1, p3, p4, close: true, fill: rgb("#cce5ff"), stroke: black)

    circle(p1, radius: 0.1, fill: black)
    circle(p2, radius: 0.1, fill: black)
    circle(p3, radius: 0.1, fill: black)
    circle(p4, radius: 0.1, fill: black)
    content((4.5, -0.5), [3-simplex])
  }),
  caption: [Simplices of dimension 0 through 3: a vertex, edge,
    filled triangle, and tetrahedron.],
) <fig:simplex-dimensions>

For agent memory, this aligns with how knowledge emerges
from contexts. A chat or search session referencing
entities "neural networks", "backpropagation", and "gradient
descent" produces a $2$-simplex. By downward closure, this
either creates edges for pairwise co-occurrences automatically,
or implies the existence of co-occurences not yet uncovered,
ensuring consistency. This idea is generalised in the structure
of the simplicial complex through *facets*, which are the
maximal dimension proper faces of a simplex. This involves
taking the possible combinations of $k$ points of a
$k$-simplex; a $3$-simplex $s={v_1, v_2, v_3, v_4}$ will
have the facets ${v_1, v_2, v_3}$, ${v_2, v_3, v_4}$,
${v_1, v_3, v_4}$, ${v_1, v_2, v_4}$. At the same time,
the same simplex itself could be contained in another
higher-dimensional simplices representing deeper structural pattern.
Such a collection of higher-dimensional simplices are
called *cofaces*; the cofaces of a $1$-simplex
$s={v_1, v_2}$ could be something like ${v_1, v_2, v_3}$,
${v_1, v_2, v_4}$, ${v_1, v_2, v_3, v_4}$. More examples
are shown in @fig:facets-cofaces.

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Left side: Facets of a 2-simplex
    let a1 = (0, 0)
    let b1 = (2, 0)
    let c1 = (1, 1.7)

    // The 2-simplex (light fill)
    line(a1, b1, c1, close: true, fill: rgb("#e6f0ff"), stroke: black)

    // Highlight one facet (edge) in a different color
    line(a1, b1, stroke: (paint: rgb("#ff6b6b"), thickness: 2pt))

    // Vertices
    circle(a1, radius: 0.1, fill: black)
    circle(b1, radius: 0.1, fill: black)
    circle(c1, radius: 0.1, fill: black)

    // Labels
    content((0, -0.35), $v_1$)
    content((2, -0.35), $v_2$)
    content((1, 2.05), $v_3$)

    // Annotation
    content((1, -1), [2-simplex $sigma = {v_1, v_2, v_3}$])
    content((1, -1.5), text(fill: rgb("#ff6b6b"))[facet: ${v_1, v_2}$])

    // Right side: Cofaces of a 1-simplex
    let a2 = (4, 0)
    let b2 = (6, 0)
    let c2 = (5, 1.7)
    let d2 = (5, 0.6)

    // Show the edge and its cofaces (triangles containing it)
    // Back face
    line(a2, b2, c2, close: true, fill: rgb("#d4edda"), stroke: black)
    // Front face
    line(a2, b2, d2, close: true, fill: rgb("#fff3cd"), stroke: black)

    // Highlight the original 1-simplex
    line(a2, b2, stroke: (paint: rgb("#4a90d9"), thickness: 3pt))

    // Vertices
    circle(a2, radius: 0.1, fill: black)
    circle(b2, radius: 0.1, fill: black)
    circle(c2, radius: 0.1, fill: black)
    circle(d2, radius: 0.1, fill: black)

    // Labels
    content((4, -0.35), $v_1$)
    content((6, -0.35), $v_2$)
    content((5, 2.05), $v_3$)
    content((5.4, 0.6), $v_4$)

    // Annotation
    content((5, -1), text(fill: rgb("#4a90d9"))[1-simplex $tau = {v_1, v_2}$])
    content((5, -1.5), [cofaces: ${v_1, v_2, v_3}$, ${v_1, v_2, v_4}$])
  }),
  caption: [Left: A facet of the 2-simplex ${v_1, v_2, v_3}$ is the edge
    ${v_1, v_2}$ (highlighted in red). Right: Cofaces of the 1-simplex
    ${v_1, v_2}$ (highlighted in blue) are the 2-simplices containing it.],
) <fig:facets-cofaces>

These structures support natural memory operations. Coface
lookup retrieves higher-dimensional simplices containing
a query, identifying stronger contextual and narrative
associations. Facet traversal descends to lower-dimensional faces,
broadening the search when specificity must be relaxed.

When an agent retrieves knowledge relevant to a query, the
retrieved simplices form a *subcomplex*, a simplicial complex
$K^(')=(V^('), S^('))$ satisfying $V^(') subset.eq V$ and $S^(') subset.eq S$.
However, behavioral data does not arrive in face-respecting
order. A user may discuss entities ${v_1, v_2, v_3}$ together
before ever discussing ${v_1, v_2}$ in isolation. The
downward closure property defines a simplicial complex
mathematically, but operational efficiency favours a
different approach: we insert only directly observed
simplices without materializing implied faces. A
conversation yielding co-occurring entities ${v_1, v_2, v_3}$
produces a single 2-simplex insertion rather than the seven
insertions required for full closure. At query time, faces
that exist in the database represent independently confirmed
co-occurrences, while faces computable from higher-dimensional
simplices but absent from storage represent knowledge
gaps—co-occurrences implied by context but never directly
observed.

Given a query-induced subcomplex formed by retrieving
cofaces of semantically matched vertices, we enumerate the
theoretical faces of each retrieved coface and check their
existence in storage. Notably, we do _not_ enumerate all
$2^n - 1$ faces of the matched vertex set directly; instead,
gap detection operates within each coface independently.
This preserves the clustering structure established during
witness complex construction: each coface represents a
coherent context (a temporal session or location), and
gaps within that context signal missing relationships
that share semantic grounding. Cross-context gaps (between
vertices that never co-occurred in any coface) would lack
this grounding and produce less actionable signals.

Faces that are combinatorially required within a coface
but absent from the database represent knowledge gaps
local to that context: the system has evidence that
entities co-occur in some higher-order relationship,
but lacks direct confirmation of the supporting lower-order
structure. The agent may then pose clarifying questions to
confirm these missing relationships, or discount confidence
in inferences that depend on unobserved faces.

This integrates naturally with *filtration*. A filtration of
simplicial complex $K$ is an ordering of $K$ such that all
prefixes are subcomplexes of $K$. That is, for two simplices
$sigma, tau$ in $K$ such that $sigma subset tau$, $sigma$
appears before $tau$ in the ordering. For example, consider
building a filled triangle ${v_1, v_2, v_3}$. A valid filtration
orders the simplices as:

$
  {v_1} -> {v_2} -> {v_3} -> {v_1,v_2} -> \ {v_2,v_3} -> {v_1,v_3} -> {v_1,v_2,v_3}
$

Each prefix forms a valid subcomplex: vertices appear before
edges, and edges before the filled face (@fig:filtration).

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Step 1: vertices only
    let y = 2.2
    circle((0, y), radius: 0.08, fill: black)
    circle((1, y), radius: 0.08, fill: black)
    circle((0.5, y + 0.85), radius: 0.08, fill: black)
    content((0.5, y - 0.5), $t_1$)

    // Step 2: one edge
    let x2 = 1.8
    line((x2, y), (x2 + 1, y), stroke: black)
    circle((x2, y), radius: 0.08, fill: black)
    circle((x2 + 1, y), radius: 0.08, fill: black)
    circle((x2 + 0.5, y + 0.85), radius: 0.08, fill: black)
    content((x2 + 0.5, y - 0.5), $t_2$)

    // Step 3: two edges
    let x3 = 3.6
    line((x3, y), (x3 + 1, y), stroke: black)
    line((x3 + 1, y), (x3 + 0.5, y + 0.85), stroke: black)
    circle((x3, y), radius: 0.08, fill: black)
    circle((x3 + 1, y), radius: 0.08, fill: black)
    circle((x3 + 0.5, y + 0.85), radius: 0.08, fill: black)
    content((x3 + 0.5, y - 0.5), $t_3$)

    // Step 4: three edges (empty triangle)
    let x4 = 5.4
    line((x4, y), (x4 + 1, y), stroke: black)
    line((x4 + 1, y), (x4 + 0.5, y + 0.85), stroke: black)
    line((x4 + 0.5, y + 0.85), (x4, y), stroke: black)
    circle((x4, y), radius: 0.08, fill: black)
    circle((x4 + 1, y), radius: 0.08, fill: black)
    circle((x4 + 0.5, y + 0.85), radius: 0.08, fill: black)
    content((x4 + 0.5, y - 0.5), $t_4$)

    // Step 5: filled triangle
    let x5 = 2.7
    let y5 = 0
    line(
      (x5, y5),
      (x5 + 1, y5),
      (x5 + 0.5, y5 + 0.85),
      close: true,
      fill: rgb("#cce5ff"),
      stroke: black,
    )
    circle((x5, y5), radius: 0.08, fill: black)
    circle((x5 + 1, y5), radius: 0.08, fill: black)
    circle((x5 + 0.5, y5 + 0.85), radius: 0.08, fill: black)
    content((x5 + 0.5, y5 - 0.5), $t_5$)
  }),
  caption: [A filtration building a 2-simplex. At $t_1$, only vertices exist.
    Edges are added at $t_2$-$t_4$. The filled 2-simplex appears at $t_5$,
    only after all its faces exist.],
) <fig:filtration>

Rather than treating filtration as a global property,
we compute it over the query-induced subcomplex.
Closure-induced faces can be flagged for inference.
The agent may then pose clarifying questions or bias search
results to confirm missing relationships, or discount
confidence in inferences that depend on closure-induced faces.
The topology of the query-induced subcomplex thus serves
not only as a retrieval mechanism but as an inference
guide, directing attention toward gaps most relevant
to the immediate task.

= Simplex Trees
The simplex tree, introduced by Boissonnat and Maria in
2014, provides an efficient data structure for
representing abstract simplicial complexes of
arbitrary dimension@boissonnat2020. The simplex tree
reconciles the need to explicitly store all faces of the
complex with the desire for compact representation and
efficient operations, making it particularly well-suited
for database-backed memory systems.

#pagebreak()

For the simplicial complex $K=(V, S)$ of dimension $k$
(that is, the dimension of the largest simplex in $K$), we label each vertice $v_i in V$ a letter
$l_i in {1, ..., |V|}$ from the alphabet $1, ..., |V|$, where
$1 <= l_1 < ... < l_(|V|) <= |V|$. Then, the simplex
$s={v_1, ..., v_i}$ can be represented as the word
$[s]=[l_1, ..., l_j]$. This allows us to express every $k$-simplex $s in S$ as a word of $(k + 1)$ length with labels
of ascending order. We start with an empty *trie*, and construct
the tree as such (@fig:simplex-tree):
- Words are inserted from the root or node to the leaf of
  the tree, with the first letter as the root or node and
  the last letter as the leaf.
- If inserting a word $[s]=[l_1, ...l_j]$, and the longest
  prefix word already in the tree is ${l_1, ..., l_i}$, of
  which $i < j$, we append the rest of the word
  $[l_(i+1), ..., l_j]$ to the $l_i$ node.

#figure(
  cetz.canvas({
    import cetz.draw: *

    // Left: Simplicial complex
    // Triangle {1,2,3} + edge {2,4}
    let v1 = (0, 0)
    let v2 = (1.2, 0)
    let v3 = (0.6, 1)
    let v4 = (2.1, 0.5)

    // Filled triangle
    line(v1, v2, v3, close: true, fill: rgb("#cce5ff"), stroke: black)

    // Extra edge {2,4}
    line(v2, v4, stroke: black)

    // Vertices
    circle(v1, radius: 0.08, fill: black)
    circle(v2, radius: 0.08, fill: black)
    circle(v3, radius: 0.08, fill: black)
    circle(v4, radius: 0.08, fill: black)

    // Vertex labels
    content((-0.2, -0.05), $1$)
    content((1.2, -0.25), $2$)
    content((0.6, 1.25), $3$)
    content((2.3, 0.5), $4$)

    // Right: Simplex tree
    let tx = 5.5
    let ty = 1.2

    // Root node
    circle((tx, ty), radius: 0.15, fill: white, stroke: black)
    content((tx, ty), text(size: 7pt)[$emptyset$])

    // Level 1 nodes: 1, 2, 3, 4
    let n1 = (tx - 1.8, ty - 0.8)
    let n2 = (tx - 0.6, ty - 0.8)
    let n3 = (tx + 0.6, ty - 0.8)
    let n4 = (tx + 1.8, ty - 0.8)

    line((tx, ty - 0.15), (n1.at(0), n1.at(1) + 0.15), stroke: black)
    line((tx, ty - 0.15), (n2.at(0), n2.at(1) + 0.15), stroke: black)
    line((tx, ty - 0.15), (n3.at(0), n3.at(1) + 0.15), stroke: black)
    line((tx, ty - 0.15), (n4.at(0), n4.at(1) + 0.15), stroke: black)

    circle(n1, radius: 0.15, fill: white, stroke: black)
    circle(n2, radius: 0.15, fill: white, stroke: black)
    circle(n3, radius: 0.15, fill: white, stroke: black)
    circle(n4, radius: 0.15, fill: white, stroke: black)

    content(n1, text(size: 7pt)[$1$])
    content(n2, text(size: 7pt)[$2$])
    content(n3, text(size: 7pt)[$3$])
    content(n4, text(size: 7pt)[$4$])

    // Level 2 from node 1: 2, 3
    let n12 = (n1.at(0) - 0.4, n1.at(1) - 0.8)
    let n13 = (n1.at(0) + 0.4, n1.at(1) - 0.8)

    line(
      (n1.at(0), n1.at(1) - 0.15),
      (n12.at(0), n12.at(1) + 0.15),
      stroke: black,
    )
    line(
      (n1.at(0), n1.at(1) - 0.15),
      (n13.at(0), n13.at(1) + 0.15),
      stroke: black,
    )

    circle(n12, radius: 0.15, fill: white, stroke: black)
    circle(n13, radius: 0.15, fill: white, stroke: black)

    content(n12, text(size: 7pt)[$2$])
    content(n13, text(size: 7pt)[$3$])

    // Level 2 from node 2: 3, 4
    let n23 = (n2.at(0) - 0.4, n2.at(1) - 0.8)
    let n24 = (n2.at(0) + 0.4, n2.at(1) - 0.8)

    line(
      (n2.at(0), n2.at(1) - 0.15),
      (n23.at(0), n23.at(1) + 0.15),
      stroke: black,
    )
    line(
      (n2.at(0), n2.at(1) - 0.15),
      (n24.at(0), n24.at(1) + 0.15),
      stroke: black,
    )

    circle(n23, radius: 0.15, fill: white, stroke: black)
    circle(n24, radius: 0.15, fill: white, stroke: black)

    content(n23, text(size: 7pt)[$3$])
    content(n24, text(size: 7pt)[$4$])

    // Level 3 from node 1→2: 3
    let n123 = (n12.at(0), n12.at(1) - 0.8)

    line(
      (n12.at(0), n12.at(1) - 0.15),
      (n123.at(0), n123.at(1) + 0.15),
      stroke: black,
    )

    circle(n123, radius: 0.15, fill: white, stroke: black)

    content(n123, text(size: 7pt)[$3$])
  }),
  caption: [A simplicial complex $K$ with 2-simplex ${1,2,3}$ and edge ${2,4}$
    (left) and its simplex tree representation (right). Each path from root
    to node encodes a simplex: e.g., $emptyset -> 1 -> 2 -> 3$ represents ${1,2,3}$.],
) <fig:simplex-tree>

In the original Boissonnat and Maria paper, the simplex tree
was implemented as an in-memory structure. While in-memory
databases could host these structures directly, they are
unsuitable for persistent agent memory: RAM costs more per gigabyte than SSD storage, and requires
continuous power to retain state. In-memory stores excel as
caches, not as primary memory layers that must persist
across sessions and scale with conversation history.
We therefore implement the simplex tree using disk-backed
persistence. Translating the requirements of the in-memory
tree required some unique considerations:
1. An in-memory simplex tree uses red-black trees or hash
  tables for the trie structure, with the top nodes being
  an array. However, red-black trees are not used as database
  indexes due to being optimised for in-memory operations
  rather than disk-based operations@du2023. Hash indexes are thus
  used in place, preserving the original time complexity of operations
  in the paper. A breakdown of the time complexity of
  operations in the persistent agent memory is given in @tbl:operations.

  #figure(
    table(
      columns: 3,
      align: (left, left, left),
      table.header([*Operation*], [*Purpose*], [*Complexity*]),
      [Insert simplex],
      [Record observed co-occurrence from extraction],
      [$O(j)$],

      [Membership check],
      [Verify whether a face exists during gap detection],
      [$O(j)$],

      [Cofaces of vertex set],
      [Find all simplices containing query-matched vertices],
      [$O(k T^(>0)_("last"(v)))$],

      [Enumerate theoretical faces],
      [Compute expected faces for filtration comparison],
      [$O(2^j)$],

      [Delete simplex], [Memory management, forgetting], [$O(j)$],
    ),
    caption: [Time complexity of simplex tree operations.],
  ) <tbl:operations>

  Here, $j$ is the simplex dimension, $k$ is the dimension
  of the simplicial complex, and $T_("last"(s))^(> 0)$ is
  the total number of nodes in the simplex tree storing
  $"last"(s)$, the last letter of the simplex $s$, at a
  tree depth greater than $0$. In practice, this value is
  bounded by $C_({"last"(s)})$, the number of cofaces
  containing the last letter of the simplex.
2. In the in-memory implementation, each sibling node has
  a pointer to its parent node, and for all nodes in the
  same tree depth of the same letter label $l_i$, they
  are connected in a circular linked list. Both cases are
  achievable in the relational model by using foreign-key
  primary-key relations, which can be shown in greater
  detail in the next section.

= Database Design
We translate simplex trees to persistent database schemas
with three core tables, adapting standard approaches to
modelling graphs in relational models@kleppmann2018. The
full schema definition is provided in the Appendix.

#figure(
  render(
    ```
    erDiagram
      user_knowledge_vertex {
        SERIAL vertex_id PK
        INT user_id
        FLOAT[] embedding
        TEXT content
        JSONB meta_data
      }
      user_knowledge_edge {
        SERIAL edge_id PK
        INT user_id
        INT tail_vertex FK
        INT head_vertex FK
        FLOAT[] embedding
        TEXT content
      }
      simplex_node {
        SERIAL node_id PK
        INT user_id
        INT parent_id FK
        INT vertex_id FK
        INT depth
        TEXT type
      }
      user_knowledge_edge }o--|| user_knowledge_vertex : tail_vertex
      user_knowledge_edge }o--|| user_knowledge_vertex : head_vertex
      simplex_node }o--|| user_knowledge_vertex : vertex_id
      simplex_node }o--o| simplex_node : parent_id
    ```.text,
  ),
  caption: [Entity-relationship diagram for the persistence layer. The
    `simplex_node` table implements the trie structure with a self-referential
    foreign key for parent traversal. Both `user_knowledge_edge` and
    `simplex_node` reference vertices in `user_knowledge_vertex`.],
) <fig:er-diagram>

#pagebreak()

= Appendix

== Database Schema Definition <appendix:schema>

```sql
CREATE TABLE user_knowledge_vertex (
    vertex_id   SERIAL PRIMARY KEY,
    user_id     INT NOT NULL,
    embedding   FLOAT[] NOT NULL,
    content     TEXT NOT NULL,
    meta_data   JSONB DEFAULT '{}'
);

CREATE TABLE user_knowledge_edge (
    edge_id     SERIAL PRIMARY KEY,
    user_id     INT NOT NULL,
    tail_vertex INT REFERENCES user_knowledge_vertex(vertex_id),
    head_vertex INT REFERENCES user_knowledge_vertex(vertex_id),
    embedding   FLOAT[],
    content     TEXT,
    meta_data   JSONB DEFAULT '{}'
);

CREATE TABLE simplex_node (
    node_id     SERIAL PRIMARY KEY,
    user_id     INT NOT NULL,
    parent_id   INT REFERENCES simplex_node(node_id),
    vertex_id   INT REFERENCES user_knowledge_vertex(vertex_id),
    depth       INT NOT NULL,
    type        TEXT,
    meta_data   JSONB DEFAULT '{}'
);

-- Unique constraint handling NULL parent_id for root nodes
CREATE UNIQUE INDEX idx_simplex_unique
    ON simplex_node (user_id, parent_id, vertex_id)
    WHERE parent_id IS NOT NULL;
CREATE UNIQUE INDEX idx_simplex_root_unique
    ON simplex_node (user_id, vertex_id)
    WHERE parent_id IS NULL;

-- Child lookup (hash for O(1) expected)
CREATE INDEX idx_children
    ON simplex_node USING HASH (parent_id);

-- L_j(ℓ) lists: find all nodes referencing a vertex at given depth
CREATE INDEX idx_vertex_depth
    ON simplex_node (user_id, vertex_id, depth);

-- Parent traversal
CREATE INDEX idx_parent
    ON simplex_node (parent_id);
```


