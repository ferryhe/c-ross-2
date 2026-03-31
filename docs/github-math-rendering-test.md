# GitHub Math Rendering Test

这个文件只用于测试 GitHub Markdown 对分段公式的渲染差异。

## Variant 1: Current One-Line `$$`

$$
\mathrm {k} _ {1} = \begin{cases} - 0.05 & \mathrm {C} _ {\text {车险}} \in (0, 95\% ] \\ 0 & \mathrm {C} _ {\text {车险}} \in (95\%, 100\% ] \\ 0.05 & \mathrm {C} _ {\text {车险}} \in (100\%, 105\% ] \\ 0.1 & \mathrm {C} _ {\text {车险}} \in (105\%, +\infty) \end{cases}
$$

## Variant 2: Multi-Line `$$`

$$
\mathrm {k} _ {1} = \begin{cases}
- 0.05 & \mathrm {C} _ {\text {车险}} \in (0, 95\% ] \\
0 & \mathrm {C} _ {\text {车险}} \in (95\%, 100\% ] \\
0.05 & \mathrm {C} _ {\text {车险}} \in (100\%, 105\% ] \\
0.1 & \mathrm {C} _ {\text {车险}} \in (105\%, +\infty)
\end{cases}
$$

## Variant 3: GitHub `math` Fence

```math
\mathrm {k} _ {1} = \begin{cases}
- 0.05 & \mathrm {C} _ {\text {车险}} \in (0, 95\% ] \\
0 & \mathrm {C} _ {\text {车险}} \in (95\%, 100\% ] \\
0.05 & \mathrm {C} _ {\text {车险}} \in (100\%, 105\% ] \\
0.1 & \mathrm {C} _ {\text {车险}} \in (105\%, +\infty)
\end{cases}
```

## Variant 4: One-Line `$$` With Doubled Escapes

$$
\mathrm {k} _ {1} = \begin{cases} - 0.05 & \mathrm {C} _ {\\text {车险}} \in (0, 95\\% ] \\\\ 0 & \mathrm {C} _ {\\text {车险}} \in (95\\%, 100\\% ] \\\\ 0.05 & \mathrm {C} _ {\\text {车险}} \in (100\\%, 105\\% ] \\\\ 0.1 & \mathrm {C} _ {\\text {车险}} \in (105\\%, +\\infty) \end{cases}
$$
