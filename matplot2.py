import numpy as np 
import matplotlib.pyplot as plt
import pandas as pd

# Read and combine multiple images
file_paths = [
    "/home/alan/Desktop/workspace/space/ch3_libs/lib-v2/data/raw/20230827/ch3_lib_007_20230827T181223_01_l0/picture.csv",
    "/home/alan/Desktop/workspace/space/ch3_libs/lib-v2/data/raw/20230827/ch3_lib_007_20230827T181223_01_l0/picture2.csv",
    "/home/alan/Desktop/workspace/space/ch3_libs/lib-v2/data/raw/20230827/ch3_lib_007_20230827T181223_01_l0/picture3.csv"
]

images = []
for file_path in file_paths:
    df = pd.read_csv(file_path)
    images.append(df.values.astype(np.float32))

# Average the images
combined_image = np.mean(images, axis=0)

plt.figure(figsize=(10, 8))
plt.imshow(combined_image, cmap='gray')
plt.title("Combined/Averaged Image")
plt.colorbar()
plt.axis('off')
plt.show()
