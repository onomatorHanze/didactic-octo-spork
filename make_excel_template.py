import pandas as pd
import os

# Zorg dat de data-map bestaat
os.makedirs("data", exist_ok=True)

# Kolommen voor de quiz
cols = ["id","type","topic","text","choices","answer","explanation","image_path","formula_latex","tags","difficulty"]

# Voorbeeldinhoud
data_dc = [
    ["q1", "mc", "Ohmse wet", "Wat is de juiste formule voor de stroom I?", "['I = U/R','U = I*R','R = U/I']", 0, "Volgens de wet van Ohm geldt: I = U / R.", "assets/ohm_schema.png", "I = \\frac{U}{R}", "['DC','basis']", 2],
    ["q2", "tf", "AC/DC", "Gelijkspanning wisselt van polariteit.", "[]", False, "Dat klopt niet, gelijkspanning wisselt niet van polariteit.", "", "", "['AC','basis']", 1],
    ["q3", "input", "Vermogen", "Bereken het vermogen bij U=12V en I=1A (Watt).", "[]", 12, "P = U * I", "", "", "['DC','vermogen']", 3],
]

data_ac = [
    ["q1", "tf", "AC", "De frequentie van het lichtnet is 50 Hz.", "[]", True, "In Europa is de netfrequentie 50 Hz.", "", "", "['AC','basis']", 1],
]

# Opslaan in Excel (met meerdere tabbladen)
with pd.ExcelWriter("data/quizvragen.xlsx", engine="openpyxl") as writer:
    pd.DataFrame(data_dc, columns=cols).to_excel(writer, index=False, sheet_name="DC")
    pd.DataFrame(data_ac, columns=cols).to_excel(writer, index=False, sheet_name="AC")

print("✅ Excelbestand 'quizvragen.xlsx' aangemaakt met tabbladen DC en AC")
