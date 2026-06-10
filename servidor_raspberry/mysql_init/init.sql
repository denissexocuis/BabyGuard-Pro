CREATE TABLE sensor_logs (
id_log int auto_increment primary key,
ruido float(2),
ts timestamp default current_timestamp
);
