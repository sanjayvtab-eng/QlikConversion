# Qlik Set Analysis to Power BI DAX Conversion Guide

## 1. Basic Sum

### Qlik

```qlik
Sum(Sales)
```

### DAX

```dax
SUM(Sales[Sales])
```

---

## 2. Single Filter

### Qlik

```qlik
Sum({<Year={2025}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Year] = 2025
)
```

---

## 3. Multiple Filters

### Qlik

```qlik
Sum({<Year={2025},Region={'India'}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Year] = 2025,
    Sales[Region] = "India"
)
```

---

## 4. Count

### Qlik

```qlik
Count(CustomerID)
```

### DAX

```dax
COUNT(Sales[CustomerID])
```

---

## 5. Distinct Count

### Qlik

```qlik
Count(DISTINCT CustomerID)
```

### DAX

```dax
DISTINCTCOUNT(Sales[CustomerID])
```

---

## 6. Distinct Count with Filter

### Qlik

```qlik
Count({<Year={2025}>} DISTINCT CustomerID)
```

### DAX

```dax
CALCULATE(
    DISTINCTCOUNT(Sales[CustomerID]),
    Sales[Year] = 2025
)
```

---

## 7. Average

### Qlik

```qlik
Avg(Sales)
```

### DAX

```dax
AVERAGE(Sales[Sales])
```

---

## 8. Maximum

### Qlik

```qlik
Max(Sales)
```

### DAX

```dax
MAX(Sales[Sales])
```

---

## 9. Minimum

### Qlik

```qlik
Min(Sales)
```

### DAX

```dax
MIN(Sales[Sales])
```

---

## 10. Current Selection ($)

### Qlik

```qlik
Sum({$} Sales)
```

### DAX

```dax
SUM(Sales[Sales])
```

---

## 11. Ignore All Selections (1)

### Qlik

```qlik
Sum({1} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    ALL(Sales)
)
```

---

## 12. Remove Filter from One Column

### Qlik

```qlik
Sum({<Year=>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    ALL(Sales[Year])
)
```

---

## 13. Previous Year

### Qlik

```qlik
Sum({<Year={$(=Max(Year)-1)}>} Sales)
```

### DAX

```dax
VAR PrevYear =
    MAX(Sales[Year]) - 1

RETURN
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Year] = PrevYear
)
```

---

## 14. Current Year

### Qlik

```qlik
Sum({<Year={$(=Max(Year))}>} Sales)
```

### DAX

```dax
VAR CurrYear =
    MAX(Sales[Year])

RETURN
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Year] = CurrYear
)
```

---

## 15. YTD

### Qlik

```qlik
Sum({<Date={">=$(=YearStart(Today()))"}>} Sales)
```

### DAX

```dax
TOTALYTD(
    SUM(Sales[Sales]),
    Calendar[Date]
)
```

---

## 16. MTD

### Qlik

```qlik
Sum({<Date={">=$(=MonthStart(Today()))"}>} Sales)
```

### DAX

```dax
TOTALMTD(
    SUM(Sales[Sales]),
    Calendar[Date]
)
```

---

## 17. QTD

### Qlik

```qlik
Sum({<Date={">=$(=QuarterStart(Today()))"}>} Sales)
```

### DAX

```dax
TOTALQTD(
    SUM(Sales[Sales]),
    Calendar[Date]
)
```

---

## 18. Last 12 Months

### Qlik

```qlik
Sum({<Date={">=$(=AddMonths(Today(),-12))"}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    DATESINPERIOD(
        Calendar[Date],
        MAX(Calendar[Date]),
        -12,
        MONTH
    )
)
```

---

## 19. Exclude Value

### Qlik

```qlik
Sum({<Region-={'India'}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Region] <> "India"
)
```

---

## 20. Multiple Values

### Qlik

```qlik
Sum({<Region={'India','USA'}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Region] IN {"India","USA"}
)
```

---

## 21. Wildcard Search

### Qlik

```qlik
Sum({<Product={"A*"}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    LEFT(Sales[Product],1)="A"
)
```

---

## 22. Advanced Search

### Qlik

```qlik
Sum({<Sales={">1000"}>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Sales] > 1000
)
```

---

## 23. Alternate State

### Qlik

```qlik
Sum({State1} Sales)
```

### DAX

```dax
Not Directly Supported

Use:
- Disconnected tables
- TREATAS()
- Calculation Groups
```

---

## 24. P() Possible Values

### Qlik

```qlik
Sum({<Customer=P(Customer)>} Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    VALUES(Sales[Customer])
)
```

---

## 25. E() Excluded Values

### Qlik

```qlik
Sum({<Customer=E(Customer)>} Sales)
```

### DAX

```dax
Use EXCEPT()

VAR ExcludedCustomers =
EXCEPT(
    ALL(Sales[Customer]),
    VALUES(Sales[Customer])
)

RETURN
CALCULATE(
    SUM(Sales[Sales]),
    ExcludedCustomers
)
```

---

## 26. AGGR()

### Qlik

```qlik
Sum(Aggr(Sum(Sales), Customer))
```

### DAX

```dax
SUMX(
    VALUES(Sales[Customer]),
    CALCULATE(SUM(Sales[Sales]))
)
```

---

## 27. Nested Aggregation

### Qlik

```qlik
Avg(Aggr(Sum(Sales), Customer))
```

### DAX

```dax
AVERAGEX(
    VALUES(Sales[Customer]),
    CALCULATE(SUM(Sales[Sales]))
)
```

---

## 28. TOTAL Qualifier

### Qlik

```qlik
Sum(TOTAL Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    ALL(Sales)
)
```

---

## 29. TOTAL <Field>

### Qlik

```qlik
Sum(TOTAL <Region> Sales)
```

### DAX

```dax
CALCULATE(
    SUM(Sales[Sales]),
    ALLEXCEPT(
        Sales,
        Sales[Region]
    )
)
```

---

## 30. Dynamic Variable

### Qlik

```qlik
Sum({<Year={$(vYear)}>} Sales)
```

### DAX

```dax
VAR SelectedYear =
SELECTEDVALUE(YearTable[Year])

RETURN
CALCULATE(
    SUM(Sales[Sales]),
    Sales[Year] = SelectedYear
)
```

---

# Important Migration Notes

| Qlik Feature          | Power BI Equivalent |
| --------------------- | ------------------- |
| Set Analysis          | CALCULATE           |
| AGGR                  | SUMX / AVERAGEX     |
| P()                   | VALUES              |
| E()                   | EXCEPT              |
| TOTAL                 | ALL / ALLEXCEPT     |
| Variables             | VAR                 |
| Alternate State       | TREATAS             |
| Current Selection ($) | Filter Context      |
| Ignore Selection (1)  | ALL                 |
| Date Ranges           | DATESINPERIOD       |
| YTD                   | TOTALYTD            |
| MTD                   | TOTALMTD            |
| QTD                   | TOTALQTD            |
