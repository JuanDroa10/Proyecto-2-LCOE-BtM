from src import creg_tariffs
for ciudad in ["Cali", "Bogota", "Barranquilla", "Buenaventura"]:
    n2  = creg_tariffs.get_n2_tariff_cop_per_kwh(ciudad)
    bk  = creg_tariffs.get_agge_backup_charge_usd_per_kwp_year(ciudad, 2020)
    print(f"{ciudad:15s} N2={n2:>10.2f} COP/kWh   Backup={bk:>8.2f} USD/kWp·año")