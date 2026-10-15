-- Latest A1c per patient, keyed on LOINC 4548-4 (not display text, which varies per instance).
-- Ties on date fall back to the newest row id. Output: pubpid, lname, fname, date, value, units.
SELECT pubpid, lname, fname, DATE(date_collected) AS a1c_date, result, units
FROM (
  SELECT p.pubpid, p.lname, p.fname, rep.date_collected, res.result, res.units,
         ROW_NUMBER() OVER (PARTITION BY p.pid
                            ORDER BY rep.date_collected DESC, res.procedure_result_id DESC) AS rn
  FROM procedure_result res
  JOIN procedure_report rep ON rep.procedure_report_id = res.procedure_report_id
  JOIN procedure_order o    ON o.procedure_order_id = rep.procedure_order_id
  JOIN patient_data p       ON p.pid = o.patient_id
  WHERE res.result_code = '4548-4'
) latest
WHERE rn = 1
ORDER BY pubpid;
