import os
from astropy.io import fits
import matplotlib.pyplot as plt
import pandas as pd


# Folder containing the FITS files
folder_path = r"D:\workspace\data"

filename = "SUT_T25_1555_001472_Lev1.0_2025-10-21T15.58.55.409_0973BB02.fits"
# Loop through all files in the folder
for filename in os.listdir(folder_path):
    if filename.lower().endswith(".fits"):
        file_path = os.path.join(folder_path, filename)
        print(f"Opening file: {file_path}")
        
        # Open the FITS file
        with fits.open(file_path) as hdul:
            # Display summary info
            hdul.info()
            
            # Access data in the first HDU
            data = hdul[0].data
            header = hdul[0].header
            
            # Example: Print basic info about the image
            print(f"Data shape: {data.shape if data is not None else 'No data'}")
            print(f"Header keys: {len(header)} entries")
            print("-" * 60)
plt.imshow(data, cmap='Reds', origin='lower')
plt.colorbar()
plt.show()           


