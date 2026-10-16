-- Synthetic patients with known lab results. No real people, no PHI.
-- A1c is coded LOINC 4548-4. Expected latest values: oracle/expected_latest_a1c.tsv.

INSERT INTO patient_data (pid, pubpid, fname, lname, DOB, sex, date) VALUES
  (1,  'BH001', 'Rosa',   'Delgado',   '1961-03-14', 'Female', '2026-01-05 09:00:00'),
  (2,  'BH002', 'Marcus', 'Bell',      '1958-11-02', 'Male',   '2026-01-05 09:00:00'),
  (3,  'BH003', 'Priya',  'Raman',     '1974-07-21', 'Female', '2026-01-05 09:00:00'),
  (4,  'BH004', 'Elena',  'Delgado',   '1990-01-30', 'Female', '2026-01-05 09:00:00'),
  (5,  'BH005', 'Grace',  'Whitfield', '1952-08-17', 'Female', '2026-01-05 09:00:00'),
  (6,  'BH006', 'Thomas', 'Whitfield', '1949-05-09', 'Male',   '2026-01-05 09:00:00'),
  (7,  'BH007', 'Daniel', 'Okafor',    '1983-12-01', 'Male',   '2026-01-05 09:00:00'),
  (8,  'BH008', 'Hannah', 'Lindqvist', '1995-06-23', 'Female', '2026-01-05 09:00:00'),
  (9,  'BH009', 'Samuel', 'Brooks',    '1967-02-08', 'Male',   '2026-01-05 09:00:00'),
  (10, 'BH010', 'Mei',    'Tanaka',    '1979-10-11', 'Female', '2026-01-05 09:00:00');

-- One completed lab order with one result: order -> order_code -> report -> result.
DELIMITER //
CREATE PROCEDURE seed_lab(IN p_pid BIGINT, IN p_when DATETIME, IN p_code VARCHAR(31),
                          IN p_name VARCHAR(255), IN p_text VARCHAR(255), IN p_value VARCHAR(255),
                          IN p_units VARCHAR(31), IN p_range VARCHAR(255), IN p_abnormal VARCHAR(31))
BEGIN
  INSERT INTO procedure_order (patient_id, provider_id, date_ordered, date_collected,
                               order_status, procedure_order_type, activity)
    VALUES (p_pid, 1, p_when, p_when, 'complete', 'laboratory_test', 1);
  SET @order_id = LAST_INSERT_ID();
  INSERT INTO procedure_order_code (procedure_order_id, procedure_order_seq, procedure_code, procedure_name)
    VALUES (@order_id, 1, p_code, p_name);
  INSERT INTO procedure_report (procedure_order_id, procedure_order_seq, date_collected, date_report,
                                report_status, review_status)
    VALUES (@order_id, 1, p_when, p_when, 'final', 'reviewed');
  INSERT INTO procedure_result (procedure_report_id, result_data_type, result_code, result_text, date,
                                units, result, `range`, abnormal, result_status)
    VALUES (LAST_INSERT_ID(), 'N', p_code, p_text, p_when, p_units, p_value, p_range, p_abnormal, 'final');
END //
DELIMITER ;

SET @a1c = 'Hemoglobin A1c/Hemoglobin.total in Blood';
SET @glu = 'Glucose [Mass/volume] in Serum or Plasma';

-- BH001 Rosa Delgado: three A1c results; latest (6.9) is not the highest; glucose on the same day.
CALL seed_lab(1, '2025-04-02 09:15:00', '4548-4', 'Hemoglobin A1c', @a1c, '7.9', '%', '4.0-5.6', 'high');
CALL seed_lab(1, '2025-10-01 10:30:00', '4548-4', 'Hemoglobin A1c', @a1c, '7.4', '%', '4.0-5.6', 'high');
CALL seed_lab(1, '2026-04-08 08:45:00', '4548-4', 'Hemoglobin A1c', @a1c, '6.9', '%', '4.0-5.6', 'high');
CALL seed_lab(1, '2026-04-08 08:45:00', '2345-7', 'Glucose',        @glu, '132', 'mg/dL', '70-99', 'high');

-- BH002 Marcus Bell: one A1c result.
CALL seed_lab(2, '2026-06-15 11:00:00', '4548-4', 'Hemoglobin A1c', @a1c, '8.2', '%', '4.0-5.6', 'high');

-- BH003 Priya Raman: newest result inserted first, so "last row inserted" is not "latest".
CALL seed_lab(3, '2026-09-01 09:00:00', '4548-4', 'Hemoglobin A1c', @a1c, '6.1', '%', '4.0-5.6', 'high');
CALL seed_lab(3, '2025-09-03 09:00:00', '4548-4', 'Hemoglobin A1c', @a1c, '6.4', '%', '4.0-5.6', 'high');

-- BH004 Elena Delgado: same last name as BH001.
CALL seed_lab(4, '2026-02-11 14:20:00', '4548-4', 'Hemoglobin A1c', @a1c, '5.4', '%', '4.0-5.6', '');

-- BH005 Grace Whitfield: has labs, but no A1c.
CALL seed_lab(5, '2026-05-20 08:00:00', '2345-7', 'Glucose',        @glu, '101', 'mg/dL', '70-99', 'high');

-- BH006 to BH010: no labs.

DROP PROCEDURE seed_lab;

-- Show the chart's Labs card expanded by default (user 0 = default for all users).
-- With no row OpenEMR renders it collapsed, and its links are hidden.
INSERT INTO user_settings (setting_user, setting_label, setting_value) VALUES (0, 'labdata_ps_expand', '1');
