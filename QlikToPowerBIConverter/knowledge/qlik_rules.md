# QLIK TO POWER BI — COMPLETE MIGRATION RULEBOOK

> **Tag Legend:** `PQ` = Power Query (M Language) · `DAX` = DAX Measure/Calculated Column · `Model` = Data Model · `Visual` = Report Layer · `Both` = Both layers

---

## 1. DATA LOADING & TRANSFORMATION

*These rules cover Qlik's script-based LOAD statements and their Power Query (M) equivalents.*

> 📝 Power Query (PQ) tag = done in Power Query Editor (M language). DAX tag = done in DAX measures/calculated columns.

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `LOAD ... FROM` | Import Data / Power Query | Basic import. Use Get Data → choose source. | PQ |
| `LOAD ... INLINE` | Enter Data | Hardcoded table. Use Home → Enter Data in PQ. | PQ |
| `Resident Load` | Reference Query | Right-click query → Reference to reuse without reloading. | PQ |
| `Concatenate LOAD` | Append Queries | Home → Append Queries → choose tables. | PQ |
| `NoConcatenate` | Separate queries (default behavior) | PQ doesn't auto-concatenate; each query is independent. | PQ |
| `JOIN (LOAD)` | Merge Queries | Home → Merge Queries. Choose join type: Inner/Left/Right/Full. | PQ |
| `LEFT JOIN` | Left Outer Merge | All rows from left, matching rows from right. | PQ |
| `INNER JOIN` | Inner Merge | Only matching rows from both. | PQ |
| `OUTER JOIN` | Full Outer Merge | All rows from both tables. | PQ |
| `KEEP (Left/Right/Inner)` | Merge + keep only keys | Use Merge then remove expanded columns from right side. | PQ |
| `Crosstable LOAD` | Unpivot Columns | Transform → Unpivot Columns / Unpivot Other Columns. | PQ |
| `Generic LOAD` | Pivot / Unpivot | Use Unpivot then Pivot to normalize generic key-value structure. | PQ |
| `LOAD ... WHERE ...` | Filter Rows | Home → Remove Rows → Remove Rows (with condition). | PQ |
| `LOAD ... GROUP BY` | Group By | Transform → Group By. Set aggregations per column. | PQ |
| `DISTINCT` | Remove Duplicates | Home → Remove Duplicates. | PQ |
| `AutoNumber()` | Index Column | Add Column → Index Column. Starts at 0 or 1. | PQ |
| `RowNo()` | Index Column | Add Column → Index Column → From 1. | PQ |
| `RecNo()` | Index Column | Similar to RowNo(). Use Index Column. | PQ |
| `LOAD ... ORDER BY` | Sort Rows | Home → Sort Ascending/Descending. | PQ |
| `LOAD ... LIMIT n` | Keep Top Rows | Home → Keep Rows → Keep Top Rows. | PQ |
| `LOAD … SAMPLE n` | Keep Every Nth Row | Home → Keep Rows → Keep Every Other Row or custom M step. | PQ |

---

## 2. LOOKUP & MAPPING FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `ApplyMap(mapName, key, default)` | `LOOKUPVALUE(result_col, search_col, key, [default])` | Direct equivalent. Most common Qlik pattern. | DAX |
| `ApplyMap() for bulk join` | Merge Query + Expand Column | More efficient for large datasets than row-by-row DAX. | PQ |
| `Lookup(ret_fld, match_fld, val, tbl)` | `LOOKUPVALUE(result_col, search_col, key)` | Single value lookup across tables. | DAX |
| `Exists(fld, val)` | `CONTAINS(table, col, val)` | Returns TRUE if value exists in a column. | DAX |
| `Exists(fld)` | `LOOKUPVALUE() <> BLANK()` | Check if current row's field exists in another table. | DAX |
| `Peek(fld, -1)` | `OFFSET(-1, , ORDERBY(...))` | Access previous row value. DAX 2022+. | DAX |
| `Peek(fld, n)` | `INDEX(n, ORDERBY(...))` | Access nth row value in ordered context. | DAX |
| `Previous(fld)` | `OFFSET(-1, , ORDERBY(...))` | Previous row in sequence. Same as Peek(fld,-1). | DAX |
| `FieldValue(fld, n)` | `SELECTCOLUMNS + INDEX` | Get nth distinct value of a field. | DAX |
| `FieldIndex(fld, val)` | `RANKX(ALL(col), col,,ASC,DENSE)` | Get ordinal position of a value in a field list. | DAX |

### LOOKUPVALUE Example

```dax
-- Qlik: ApplyMap('ProductMap', ProductID, 'Unknown')
-- Power BI DAX:
ProductName = LOOKUPVALUE(
    Products[ProductName],
    Products[ProductID], Sales[ProductID],
    "Unknown"
)
```

---

## 3. DATE & TIME FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Today()` | `TODAY()` | Returns today's date (no time component). | DAX |
| `Now()` | `NOW()` | Returns current date and time. | DAX |
| `Date(num, fmt)` | `FORMAT(date, format_string)` | Format date as text. e.g. `FORMAT(dt,'DD-MMM-YYYY')`. | DAX |
| `Year(date)` | `YEAR(date)` | Extracts year as integer. | DAX |
| `Month(date)` | `MONTH(date)` | Returns month number 1–12. | DAX |
| `Day(date)` | `DAY(date)` | Returns day of month 1–31. | DAX |
| `Week(date)` | `WEEKNUM(date, 2)` | ISO week. Use mode 2 for Monday start. | DAX |
| `WeekDay(date)` | `WEEKDAY(date, 2)` | Day of week. Mode 2 = Mon=1 … Sun=7. | DAX |
| `Hour(date)` | `HOUR(datetime)` | Returns hour 0–23. | DAX |
| `Minute(date)` | `MINUTE(datetime)` | Returns minute 0–59. | DAX |
| `Second(date)` | `SECOND(datetime)` | Returns second 0–59. | DAX |
| `Quarter(date)` | `QUARTER(date)` | Returns quarter 1–4. | DAX |
| `MonthName(date)` | `FORMAT(date, "MMM YYYY")` | Returns 'Jan 2025' style label. | DAX |
| `AddMonths(date, n)` | `EDATE(date, n)` | Add/subtract months. Negative n = subtract. | DAX |
| `MonthStart(date)` | `EOMONTH(date, -1) + 1` | First day of the month. | DAX |
| `MonthEnd(date)` | `EOMONTH(date, 0)` | Last day of the month. | DAX |
| `QuarterStart(date)` | `DATE(YEAR(d), (QUARTER(d)-1)*3+1, 1)` | First day of current quarter. | DAX |
| `QuarterEnd(date)` | `EOMONTH(d, 3 - MONTH(d) MOD 3)` | Last day of current quarter. | DAX |
| `YearStart(date)` | `DATE(YEAR(date), 1, 1)` | First day of year. | DAX |
| `YearEnd(date)` | `DATE(YEAR(date), 12, 31)` | Last day of year. | DAX |
| `WeekStart(date)` | `date - WEEKDAY(date,2) + 1` | Monday of the current week. | DAX |
| `WeekEnd(date)` | `date + (7 - WEEKDAY(date,2))` | Sunday of the current week. | DAX |
| `NetworkDays(d1, d2)` | `NETWORKDAYS(d1, d2)` | Working days between two dates (built-in DAX 2023+). | DAX |
| `DayNumberOfYear(d)` | `d - DATE(YEAR(d),1,1) + 1` | Day number within the year (1–365). | DAX |
| `YearToDate flag` | `DATESYTD()` | Use DATESYTD() inside CALCULATE for YTD. | DAX |
| `Interval(n, fmt)` | `FORMAT(n * 86400, ...)` | Duration formatting. Convert seconds manually. | DAX |

### Date Intelligence Examples

```dax
-- YTD Sales
Sales YTD = CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[Date]))

-- MTD Sales
Sales MTD = CALCULATE(SUM(Sales[Amount]), DATESMTD('Date'[Date]))

-- Same Period Last Year
Sales SPLY = CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date]))

-- Rolling 12 Months
Sales R12M = CALCULATE(SUM(Sales[Amount]),
    DATESINPERIOD('Date'[Date], LASTDATE('Date'[Date]), -12, MONTH))
```

---

## 4. STRING FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Len(str)` | `LEN(text)` | Length of string in characters. | DAX |
| `Left(str, n)` | `LEFT(text, n)` | Leftmost n characters. | DAX |
| `Right(str, n)` | `RIGHT(text, n)` | Rightmost n characters. | DAX |
| `Mid(str, start, n)` | `MID(text, start, n)` | Substring from position. 1-based index. | DAX |
| `Upper(str)` | `UPPER(text)` | Converts to uppercase. | DAX |
| `Lower(str)` | `LOWER(text)` | Converts to lowercase. | DAX |
| `Trim(str)` | `TRIM(text)` | Removes leading/trailing spaces. | DAX |
| `LTrim(str)` | `Text.TrimStart(text)` | Left trim only. Use Power Query M function. | PQ |
| `RTrim(str)` | `Text.TrimEnd(text)` | Right trim only. Use Power Query M function. | PQ |
| `Replace(str, f, r)` | `SUBSTITUTE(text, old_text, new_text, [n])` | Replace text. SUBSTITUTE replaces all or nth occurrence. | DAX |
| `Index(str, sub, n)` | `SEARCH(sub, text, [start])` | Find position. 1-based. Returns error if not found. | DAX |
| `Concat(agg)` | `CONCATENATEX(table, expr, delim, sort)` | Aggregated string concatenation over rows. | DAX |
| `& (concatenation)` | `& (concatenation)` | Direct string joining: `[Col1] & " " & [Col2]`. | DAX |
| `SubField(str, delim, n)` | `Text.Split(text, delim){n-1}` | Split and return nth part. PQ uses 0-based index. | PQ |
| `TextBetween(s,d1,d2)` | `MID(s, SEARCH(d1,s)+1, SEARCH(d2,s)-SEARCH(d1,s)-1)` | Extract text between two delimiters. | DAX |
| `Capitalize(str)` | `Text.Proper(text)` | Proper case in Power Query. | PQ |
| `Num(val, fmt)` | `FORMAT(value, format_string)` | Number formatted as text string. | DAX |
| `Num#(str)` | `VALUE(text)` | Parse text as a number. | DAX |
| `Date#(str, fmt)` | `DATEVALUE(text)` | Parse text string as a date. | DAX |
| `Time#(str, fmt)` | `TIMEVALUE(text)` | Parse text string as a time. | DAX |
| `Evaluate(str)` | *(no direct equivalent)* | Dynamic expression eval not supported in DAX. | DAX |
| `Hash128/Hash160` | `Binary.ToText(Crypto.Hash...)` | Use Power Query for hash functions. | PQ |
| `Ord(char)` | `Character.ToNumber(char)` | Character to ASCII code. | PQ |
| `Chr(n)` | `Character.FromNumber(n)` | ASCII code to character. | PQ |
| `Repeat(str, n)` | `Text.Repeat(text, count)` | Repeat string n times. | PQ |
| `Space(n)` | `REPT(" ", n)` | Create n spaces. | DAX |

---

## 5. CONDITIONAL FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `If(cond, then, else)` | `IF(logical, val_true, val_false)` | Direct equivalent. Can be nested. | DAX |
| `If(c1, v1, If(c2, v2, ...))` | `SWITCH(TRUE(), c1,v1, c2,v2, else_val)` | Use SWITCH(TRUE()) for nested IF chains. | DAX |
| `Pick(n, v1, v2, ...)` | `SWITCH(n, 1,v1, 2,v2, ..., else_val)` | Pick by position. Use SWITCH with integer key. | DAX |
| `Match(val, v1, v2, ...)` | `SWITCH(val, v1,'match1', v2,'match2', ...)` | Match value against list. | DAX |
| `WildMatch(val, 'A*')` | `CONTAINSSTRING(text, search)` | Wildcard check. No regex in DAX — use SEARCH(). | DAX |
| `WildMatch(v, '*A*')` | `IF(SEARCH("A", text, 1, 0) > 0, ...)` | Contains pattern check. | DAX |
| `Alt(v1, v2, v3)` | `COALESCE(v1, v2, v3)` | Return first non-null value. | DAX |
| `IsNull(val)` | `ISBLANK(value)` | TRUE if value is null/blank. | DAX |
| `Null()` | `BLANK()` | Null/blank literal value. | DAX |
| `IsNum(val)` | `ISNUMBER(value)` | TRUE if value is numeric. | DAX |
| `IsText(val)` | `ISTEXT(value)` or `NOT ISNUMBER()` | TRUE if value is text. | DAX |
| `IsDate(val)` | `Value.Is(val, type date)` | Check for date type. Use Power Query. | PQ |
| `Class(val, size)` | `INT(val / size) * size` | Bin into class intervals. Use INT for bucketing. | DAX |
| `IF + Set Analysis` | `CALCULATE(SUM(), filter...)` | Conditional aggregation goes into CALCULATE. | DAX |

### SWITCH(TRUE()) Pattern — Replaces nested IFs

```dax
-- Qlik: If(Sales>10000,'High', If(Sales>5000,'Mid','Low'))
-- Power BI:
Category =
SWITCH(TRUE(),
    Sales[Amount] > 10000, "High",
    Sales[Amount] > 5000,  "Mid",
    "Low"
)
```

---

## 6. AGGREGATION FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Sum(Sales)` | `SUM(table[col])` | Simple sum. Always reference table[col]. | DAX |
| `Sum(expr)` | `SUMX(table, expression)` | Row-by-row calculated sum. | DAX |
| `Avg(Sales)` | `AVERAGE(table[col])` | Arithmetic mean. | DAX |
| `Avg(expr)` | `AVERAGEX(table, expression)` | Row-by-row calculated average. | DAX |
| `Count(fld)` | `COUNT(table[col])` | Count non-blank values. | DAX |
| `Count(DISTINCT fld)` | `DISTINCTCOUNT(table[col])` | Count unique values. | DAX |
| `CountIf(expr)` | `COUNTROWS(FILTER(table, condition))` | Count rows matching condition. | DAX |
| `Max(fld)` | `MAX(table[col])` | Maximum value. | DAX |
| `Max(expr)` | `MAXX(table, expression)` | Max of row-level expression. | DAX |
| `Min(fld)` | `MIN(table[col])` | Minimum value. | DAX |
| `Min(expr)` | `MINX(table, expression)` | Min of row-level expression. | DAX |
| `Only(fld)` | `SELECTEDVALUE(col, [alt_result])` | Returns single value if only one is selected. | DAX |
| `Mode(fld)` | `MINX(TOPN(1, ADDCOLUMNS(...)))` | No built-in MODE. Use TOPN workaround. | DAX |
| `Median(fld)` | `MEDIAN(table[col])` | Median value. | DAX |
| `Stdev(fld)` | `STDEV.P` / `STDEV.S` | Population vs sample standard deviation. | DAX |
| `Fractile(fld, n)` | `PERCENTILE.INC(col, n)` | Percentile value. n between 0 and 1. | DAX |
| `RangeSum(a, b, c)` | `SUMX({a,b,c}, [Value])` | Sum a list of values. | DAX |
| `RangeAvg(a, b, ...)` | `AVERAGEX({...}, [Value])` | Average of a list of values. | DAX |
| `RangeMax(a, b, ...)` | `MAXX({...}, [Value])` | Max of a list. | DAX |
| `RangeMin(a, b, ...)` | `MINX({...}, [Value])` | Min of a list. | DAX |
| `FirstSortedValue(fld, sort)` | `MINX(TOPN(1, tbl, sortcol, ASC), col)` | Value from first sorted row. | DAX |
| `LastSortedValue(fld, sort)` | `MINX(TOPN(1, tbl, sortcol, DESC), col)` | Value from last sorted row. | DAX |
| `Concat(fld, delim)` | `CONCATENATEX(tbl, col, delim, col, ASC)` | Aggregated text concat with delimiter. | DAX |

---

## 7. SET ANALYSIS → CALCULATE / FILTER

*Qlik Set Analysis modifies the selection context. In Power BI, this is replaced by `CALCULATE()` with filter arguments.*

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Sum({<Year={2025}>} Sales)` | `CALCULATE(SUM(Sales[Amt]), Sales[Year]=2025)` | Filter by single value. | DAX |
| `Sum({<Year={2024,2025}>} Sales)` | `CALCULATE(SUM(Sales[Amt]), Sales[Year] IN {2024,2025})` | Filter by multiple values. | DAX |
| `Sum({1} Sales)` | `CALCULATE(SUM(Sales[Amt]), ALL(Sales))` | Ignore all selections (whole table). | DAX |
| `Sum({1<Year={2025}>} Sales)` | `CALCULATE(SUM(Sales[Amt]), ALL(Sales), Sales[Year]=2025)` | Ignore context, add new filter. | DAX |
| `Sum({$} Sales)` | `CALCULATE(SUM(Sales[Amt]))` | Default selection = current context. | DAX |
| `Sum({$<Year=>} Sales)` | `CALCULATE(SUM(Sales[Amt]), REMOVEFILTERS(Sales[Year]))` | Remove filter on Year only. | DAX |
| `Sum({$<Region-={'East'}>} Sales)` | `CALCULATE(SUM(Sales[Amt]), Sales[Region]<>"East")` | Exclude a specific value. | DAX |
| `Sum({$<Year={'>2022'}>} Sales)` | `CALCULATE(SUM(Sales[Amt]), Sales[Year] > 2022)` | Range condition filter. | DAX |
| `Sum({<Region=P(Region)>} Sales)` | `CALCULATE(SUM(Sales[Amt]), ALLSELECTED(Sales[Region]))` | Preserve user's slicer selection. | DAX |
| `Count({<Status={'Active'}>} Cust)` | `CALCULATE(COUNT(Cust[ID]), Cust[Status]="Active")` | Filtered count. | DAX |
| `Sum({Set1+Set2} Sales)` | `CALCULATE(SUM(), KEEPFILTERS(...))` | Union of sets. Use multiple CALCULATE. | DAX |
| `Sum({Set1*Set2} Sales)` | `CALCULATE(SUM(), filter1, filter2)` | Intersection = stack filters. | DAX |
| `Set variable $MySet = ...` | Reusable measure calling CALCULATE | No Set variables in DAX. Use measures. | DAX |

### Advanced CALCULATE Patterns

```dax
-- ALL(): Ignore all filters on a table
Total Sales = CALCULATE(SUM(Sales[Amount]), ALL(Sales))

-- ALLEXCEPT(): Ignore all filters except specified ones
Sales by Region = CALCULATE(
    SUM(Sales[Amount]),
    ALLEXCEPT(Sales, Sales[Region])
)

-- KEEPFILTERS(): Intersect with existing context
Sales Filtered = CALCULATE(
    SUM(Sales[Amount]),
    KEEPFILTERS(Sales[Year] = 2025)
)

-- REMOVEFILTERS(): Remove specific column filter
All Years Total = CALCULATE(
    SUM(Sales[Amount]),
    REMOVEFILTERS(Sales[Year])
)
```

---

## 8. INTER-RECORD (ROW CONTEXT) FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Above(expr)` | `OFFSET(-1, , ORDERBY(key))` | Value from previous row by sort order. | DAX |
| `Below(expr)` | `OFFSET(+1, , ORDERBY(key))` | Value from next row. | DAX |
| `Above(TOTAL expr)` | `CALCULATE(expr, ALL(table))` | Apply over all rows ignoring dim context. | DAX |
| `Previous(expr)` | `OFFSET(-1, , ORDERBY(date))` | Typically used with date ordering. | DAX |
| `Peek(fld, -1)` | `OFFSET(-1, , ORDERBY(id))` | Peek at prior row in load order. | DAX |
| `Peek(fld, 0)` | `SELECTEDVALUE(col)` or current row | Peek at current row value. | DAX |
| `Peek(fld, n)` | `INDEX(n, ORDERBY(...))` | Absolute row position n. | DAX |
| `RowNo(TOTAL)` | `RANKX(ALL(table), key,,ASC,Dense)` | Row number across all rows. | DAX |
| `RowNo()` | `RANKX(table, key,,ASC,Dense)` | Row number within current context. | DAX |
| `Column(n)` | Index column in matrix | No direct equivalent. Restructure visual. | Visual |
| `After(expr)` | `OFFSET()` in table context | Next column in a pivot — use matrix visual. | Visual |
| `Before(expr)` | `OFFSET()` in table context | Previous column in a pivot. | Visual |
| `NoOfRows()` | `COUNTROWS(table)` | Count of rows in a table/context. | DAX |

### Running Total Pattern (replaces Above/RangeSum)

```dax
-- Qlik: RangeSum(Above(Sales, 0, RowNo()))
-- Power BI Running Total:
Running Total =
CALCULATE(
    SUM(Sales[Amount]),
    'Date'[Date] <= MAX('Date'[Date])
)
```

---

## 9. MATHEMATICAL & STATISTICAL FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Round(n, step)` | `ROUND(number, decimals)` | Rounds to specified decimal places. | DAX |
| `RoundUp(n, step)` | `ROUNDUP(number, decimals)` | Always rounds away from zero. | DAX |
| `RoundDown(n, step)` | `ROUNDDOWN(number, decimals)` | Always rounds toward zero. | DAX |
| `Ceil(n, step)` | `CEILING(number, significance)` | Rounds up to nearest multiple. | DAX |
| `Floor(n, step)` | `FLOOR(number, significance)` | Rounds down to nearest multiple. | DAX |
| `Fabs(n)` / `Abs(n)` | `ABS(number)` | Absolute value. | DAX |
| `Mod(n, d)` | `MOD(number, divisor)` | Remainder after division. | DAX |
| `Pow(base, exp)` | `POWER(number, power)` | Raise to a power. | DAX |
| `Sqrt(n)` | `SQRT(number)` | Square root. | DAX |
| `Rand()` | `RAND()` | Random number 0 to <1. Recalculates each eval. | DAX |
| `Log(n, base)` | `LOG(number, base)` | Logarithm. Default base 10. | DAX |
| `Log10(n)` | `LOG10(number)` | Base-10 logarithm. | DAX |
| `Ln(n)` | `LN(number)` | Natural logarithm. | DAX |
| `Exp(n)` | `EXP(number)` | e raised to the power of n. | DAX |
| `Sin/Cos/Tan(n)` | `SIN()` / `COS()` / `TAN()` | Trigonometric functions (radians). | DAX |
| `Asin/Acos/Atan(n)` | `ASIN()` / `ACOS()` / `ATAN()` | Inverse trig (result in radians). | DAX |
| `Combin(n, k)` | `COMBIN(n, k)` | Combinations nCk. | DAX |
| `Permut(n, k)` | `PERMUT(n, k)` | Permutations nPk. | DAX |
| `Fact(n)` | `FACT(n)` | Factorial. | DAX |
| `Sign(n)` | `SIGN(n)` | Returns -1, 0, or 1. | DAX |
| `Even(n)` / `Odd(n)` | `Number.IsEven(n)` | Check parity in Power Query. | PQ |

---

## 10. VARIABLES & PARAMETERS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `LET vName = expr;` | `VAR Name = expression  RETURN ...` | DAX VAR/RETURN replaces Qlik LET. | DAX |
| `SET vName = 'string';` | `VAR Name = "string"` | String variable in measure. | DAX |
| `$(vName) substitution` | Direct measure reference | No variable substitution in DAX — reference measures. | DAX |
| `Dollar-sign expansion` | Measure / Calc column reference | DAX evaluates expressions, not text substitution. | DAX |
| `Input Box parameter` | What-if Parameter (slicer-driven) | Modeling → New Parameter for user input. | Model |
| `Slider object` | Numeric Range Slicer | Insert → Slicer → numeric field. | Visual |
| `Dynamic expression via var` | Calculation Group / Field Parameters | Field Parameters allow switching measures dynamically. | Model |

### DAX VAR / RETURN Pattern

```dax
-- Qlik: LET vTarget = 100000;
--        Sum(Sales) / $(vTarget)

-- Power BI DAX:
Sales vs Target =
VAR Target = 100000
VAR ActualSales = SUM(Sales[Amount])
RETURN
    DIVIDE(ActualSales, Target, 0)
```

---

## 11. FILTER CONTEXT & CONTEXT TRANSITIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `TOTAL qualifier` | `ALL()` inside CALCULATE | Removes dimension context from calculation. | DAX |
| `TOTAL <dim>` | `ALLEXCEPT(table, dim)` | Total across all but specified dimension. | DAX |
| `Aggr(Sum(Sales), Region)` | `SUMMARIZE` / `ADDCOLUMNS` | Virtual grouped aggregation. | DAX |
| `Aggr(Sum(Sales), [Dim])` | `SUMX(VALUES(dim), CALCULATE(SUM()))` | Iterate unique values and aggregate. | DAX |
| `P() — possible values` | `ALLSELECTED(col)` | Values passing current slicer selection. | DAX |
| `E() — excluded values` | `EXCEPT(ALL(col), ALLSELECTED(col))` | Values excluded by current selection. | DAX |
| `Selection state` | `ISFILTERED()` / `ISCROSSFILTERED()` | Check if a column has an active filter. | DAX |
| `GetCurrentField()` | `SELECTEDVALUE(col)` | Current selected value in filter context. | DAX |
| `GetFieldSelections()` | `CONCATENATEX(ALLSELECTED(col), col, ", ")` | List all selected values. | DAX |

### AGGR() → SUMX(VALUES()) Pattern

```dax
-- Qlik: Sum(Aggr(Sum(Sales), CustomerID))
-- Meaning: First sum Sales per customer, then sum those totals

-- Power BI equivalent:
Sales by Customer Sum =
SUMX(
    VALUES(Sales[CustomerID]),
    CALCULATE(SUM(Sales[Amount]))
)
```

---

## 12. RANKING & SORTING FUNCTIONS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `Rank(Total expr)` | `RANKX(ALL(table), measure,,DESC,Dense)` | Dense rank across all rows. | DAX |
| `Rank(expr)` | `RANKX(table, measure,,DESC,Dense)` | Rank within current filter context. | DAX |
| `Rank(expr, 'a')` | `RANKX(ALL(table), measure,,ASC,Dense)` | Ascending rank. | DAX |
| `Rank(expr, mode, 's')` | `RANKX(..., , , ,Skip)` | Skip ties (standard competition rank). | DAX |
| `Top(n)` | `TOPN(n, table, measure)` | Return top n rows by measure. | DAX |
| `Bottom(n)` | `TOPN(n, table, measure, ASC)` | Return bottom n rows. | DAX |
| `TopPercent(n%)` | TOPN with % logic via VAR | Top n% by value. No direct equivalent. | DAX |
| `Tile(n, count)` | `INT((RANKX(...) - 1) / count_per_tile)` | Bucket rows into n tiles (quantiles). | DAX |
| `KMeans2D()` / `KMeansND()` | Python/R visual or external ML | No native K-Means. Use Python visual. | Visual |

### TOP N Filter Pattern

```dax
-- Show only Top 10 customers by sales
IsTop10 =
VAR CustomerRank =
    RANKX(ALL(Customer[Name]), [Total Sales],,DESC,Dense)
RETURN
    IF(CustomerRank <= 10, 1, 0)

-- Then use IsTop10 = 1 as a visual filter
```

---

## 13. TABLE FUNCTIONS (DAX)

*These are used inside CALCULATE, measures, or to create calculated tables.*

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| `LOAD (all rows)` | `ALL(table)` / `ALL(col)` | Returns all rows regardless of filter. | DAX |
| `resident table` | `ALLNOBLANKROW(table)` | All rows except blank row. | DAX |
| `DISTINCT in LOAD` | `DISTINCT(table)` / `VALUES(col)` | Unique rows/values in current context. | DAX |
| `Aggr() table` | `SUMMARIZE(table, col1, "name", expr)` | Group by and aggregate. Creates virtual table. | DAX |
| `LOAD ... WHERE condition` | `FILTER(table, condition)` | Table filtered by row-level condition. | DAX |
| `LOAD ... LIMIT n` | `TOPN(n, table, sort_expr)` | Return top n rows by expression. | DAX |
| `LOAD * + new columns` | `ADDCOLUMNS(table, "col", expr)` | Extend table with calculated columns. | DAX |
| `JOIN in LOAD` | `NATURALLEFTOUTERJOIN(t1, t2)` | Join matching column names. | DAX |
| `Concatenate LOAD` | `UNION(table1, table2)` | Stack tables with same columns. | DAX |
| `CrossJoin tables` | `CROSSJOIN(table1, table2)` | Cartesian product of two tables. | DAX |
| `Except / Minus` | `EXCEPT(table1, table2)` | Rows in t1 not in t2. | DAX |
| `Intersect` | `INTERSECT(table1, table2)` | Rows present in both tables. | DAX |
| `SubTotal row` | `ROW("label", expr)` | Single-row table. Use in UNION for subtotal. | DAX |

---

## 14. DATA MODELING CONCEPTS

| Qlik Concept / Function | Power BI / DAX Equivalent | Notes & Example | Type |
|---|---|---|---|
| Associative Engine (auto-join) | Relationships in Model View | Create relationships manually in Model view. | Model |
| Key field (auto-key) | Relationship column | PBI requires explicit relationship setup. | Model |
| Synthetic key | Composite key workaround | Avoid synthetics. Create bridge tables or concat keys. | Model |
| Link table (bridge) | Bridge table relationship | Many-to-many via bridge table. | Model |
| Many-to-Many association | Many-to-Many relationship | Set relationship cardinality to M:M in PBI. | Model |
| IslandTable | Disconnected table | Slicer/parameter table not joined to model. | Model |
| Calendar / Master Calendar | Date table (Mark as Date Table) | Create date dim, mark as date table. | Model |
| Mapping table (MapLoad) | Lookup table with relationship | Small lookup tables with relationships. | Model |
| Section Access (RLS in Qlik) | Row-Level Security (RLS) | Modeling → Manage Roles. Define DAX filter. | Model |
| Binary Load | Import from Power BI Dataset (XMLA) | Reuse datasets across reports. | Model |
| Incremental Load | Incremental Refresh Policy | Premium/PPU feature. Define refresh range. | Model |
| OnDemand App | DirectQuery mode | Query live without importing all data. | Model |
| QVD cache | Import mode (cached in .pbix) | Import mode caches data in the .pbix model. | Model |

---

## 15. VISUALIZATION MAPPING

| Qlik Chart / Object | Power BI Equivalent | Notes | Type |
|---|---|---|---|
| Bar Chart | Clustered Bar/Column Chart | Use Clustered Column for vertical bars. | Visual |
| Line Chart | Line Chart | Same concept. Add secondary axis if needed. | Visual |
| Combo Chart | Line and Clustered Column Chart | Select 'Line and clustered column chart'. | Visual |
| Pie Chart | Pie Chart / Donut Chart | Donut charts are preferred in PBI. | Visual |
| Scatter Plot | Scatter Chart | Play Axis can animate over time. | Visual |
| Pivot Table | Matrix Visual | Rows, Columns, Values → Matrix fields. | Visual |
| Straight Table | Table Visual | Flat row table. Add conditional formatting. | Visual |
| Map (GeoAnalytics) | Map / Filled Map / Shape Map | Azure Maps integration in PBI. | Visual |
| Treemap | Treemap | Direct equivalent. | Visual |
| KPI Gauge | Gauge Chart / KPI Visual | KPI needs Goal, Value, and Date fields. | Visual |
| Funnel Chart | Funnel Chart | Direct equivalent. | Visual |
| Waterfall Chart | Waterfall Chart | Breakdown visual for additions/subtractions. | Visual |
| Histogram | Histogram (via Python) or Bar Chart | No native histogram. Use binned column. | Visual |
| Box Plot | Box and Whisker (AppSource visual) | Download from AppSource or use R visual. | Visual |
| Mekko Chart | Marimekko (AppSource visual) | Third-party visual from AppSource. | Visual |
| Filter Pane | Slicer | Insert → Slicer. Supports dropdown, tile, etc. | Visual |
| Current Selections Box | Smart Narrative / Filter card | No direct equivalent. Use custom visual. | Visual |
| Button (Navigation) | Button / Page Navigator | Insert → Button → Page Navigator. | Visual |
| Text Object | Text Box | Insert → Text box. | Visual |
| Bookmarks | Bookmarks Panel | View → Bookmarks. Capture view states. | Visual |
| Alternate States | Field Parameters / Bookmarks | No direct; use field params for comparisons. | Visual |

---

## 16. MIGRATION WORKFLOW (STEP-BY-STEP)

> 📝 Always start with one high-priority subject area, validate end-to-end, then scale to remaining areas.

| Step | Qlik Phase | Power BI Action | Details | Type |
|---|---|---|---|---|
| 1 | Inventory | Document all Qlik apps, data sources, LOADs | List scripts, connections, QVDs, variables, expressions. | Both |
| 2 | Data Layer | Recreate LOAD scripts in Power Query (M) | Convert LOAD → Get Data; JOIN → Merge; Concat → Append. | PQ |
| 3 | Data Model | Build relationships in Model view | Replace synthetic keys with proper relationships. | Model |
| 4 | Date Table | Create Date dimension, mark as Date Table | Auto or `CALENDARAUTO()` for date intelligence. | Model |
| 5 | RLS / Access | Configure Row-Level Security roles | Modeling → Manage Roles → define DAX filters. | Model |
| 6 | Measures | Convert Set Analysis + Expressions to DAX | `Sum({<...>} fld)` → `CALCULATE(SUM(), filter)`. | DAX |
| 7 | Variables | Replace LET/SET with VAR/RETURN or Parameters | Dynamic params → What-If or Field Parameters. | DAX |
| 8 | Dimensions | Create calculated columns / hierarchies | Calc columns for row-level expressions. | Model |
| 9 | Visuals | Rebuild charts and tables | Map Qlik chart types to PBI equivalents. | Visual |
| 10 | Validate | Cross-check totals, filters, and edge cases | Compare Qlik vs PBI numbers row by row. | Both |

---

## 17. POWER QUERY (M) QUICK REFERENCE

| Qlik Function | Power Query (M) Equivalent | Notes | Type |
|---|---|---|---|
| `Text.From()` | `Text.From(value)` | Convert any value to text. | PQ |
| `Value()` / `Num#()` | `Number.From(text)` | Parse text as number. | PQ |
| `Date#(str,fmt)` | `Date.FromText("2025-01-01")` | Parse ISO date string. | PQ |
| `Left(str, n)` | `Text.Start(text, n)` | First n characters. | PQ |
| `Right(str, n)` | `Text.End(text, n)` | Last n characters. | PQ |
| `Mid(str, s, n)` | `Text.Middle(text, offset, count)` | Substring. **PQ offset is 0-based!** | PQ |
| `Upper` / `Lower` | `Text.Upper` / `Text.Lower` | Case conversion. | PQ |
| `Trim` | `Text.Trim(text)` | Remove leading/trailing spaces. | PQ |
| `Replace()` | `Text.Replace(text, old, new)` | Replace all occurrences. | PQ |
| `SubField(str, d, n)` | `Text.Split(text, delim){n-1}` | PQ uses 0-based index in split result. | PQ |
| `Len()` | `Text.Length(text)` | Length of string. | PQ |
| `If ... Then ... End` | `if cond then val else other` | M uses lowercase if/then/else. | PQ |
| `LOAD WHERE` | `Table.SelectRows(tbl, each cond)` | Filter rows in M. | PQ |
| `GROUP BY` | `Table.Group(tbl, keys, aggs)` | Group and aggregate in M. | PQ |
| `AddColumn / Derived` | `Table.AddColumn(tbl,"name",each expr)` | Add a calculated column in PQ. | PQ |
| `LOAD first 100` | `Table.FirstN(tbl, 100)` | Keep first n rows. | PQ |
| `Sort by field` | `Table.Sort(tbl, {{col, order}})` | `Order.Ascending` or `Order.Descending`. | PQ |

---

## QUICK REFERENCE CHEAT SHEET

### Most Common Conversions

| Qlik Pattern | Power BI Pattern |
|---|---|
| `Sum({<Field={val}>} Measure)` | `CALCULATE(SUM([Measure]), Table[Field]=val)` |
| `Sum({1} Measure)` | `CALCULATE(SUM([Measure]), ALL(Table))` |
| `Aggr(Sum(Sales), Dim)` | `SUMX(VALUES(Table[Dim]), CALCULATE(SUM(Sales[Amount])))` |
| `ApplyMap('Map', Key, Default)` | `LOOKUPVALUE(Result, LookupCol, Key, Default)` |
| `Peek(Field, -1)` | `OFFSET(-1, , ORDERBY(SortCol))` |
| `Only(Field)` | `SELECTEDVALUE(Table[Field])` |
| `Alt(v1, v2, v3)` | `COALESCE(v1, v2, v3)` |
| `IsNull(v)` | `ISBLANK(v)` |
| `Rank(Total Expr)` | `RANKX(ALL(Table), [Measure],,DESC,Dense)` |
| `RangeSum(Above(X, 0, RowNo()))` | `CALCULATE(SUM(X), Date[Date] <= MAX(Date[Date]))` |
| `Resident Load` | Reference Query in Power Query |
| `Concatenate LOAD` | Append Queries in Power Query |
| `JOIN` | Merge Queries in Power Query |
| `Section Access` | Row-Level Security (RLS) |
| `Master Calendar` | Date Table (marked as Date Table) |

---

*End of Rulebook — 17 Sections · 250+ Function Mappings · All Layers Covered*
