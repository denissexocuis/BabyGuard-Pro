CREATE TABLE sensor_logs (
id_log int auto_increment primary key,
temp float(2),
humedad float(2),
ruido float(2),
ts timestamp default current_timestamp
);
