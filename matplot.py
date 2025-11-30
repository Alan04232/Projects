import numpy as np 
import matplotlib.pyplot as plt
import pandas as pd
df=pd.read_csv("/home/alan/Desktop/workspace/space/ch3_libs/lib-v2/data/raw/20230827/ch3_lib_007_20230827T181223_01_l0/picture3.csv",header=None)
"""print(df.head())  # See first few rows
print(f"\nDataFrame shape: {df.shape}")  # Check dimensions
print(f"Columns: {df.columns.tolist()}")  # See all column names
#x=np.array([1,2,3,4,5,6])"""
plt.subplot(2,2,1)
#plt.plot(x)


print(data_array.shape)

plt.imshow(data_array,cmap='viridis')
plt.colorbar()
#plt.tight_layout()  # Adjust spacing between subplots
plt.show() 
