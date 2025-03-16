import matplotlib.pyplot as plt
import cv2
import numpy as np
import os

def draw_eld_lines(hours):
    # Load the image
    image_path = os.path.abspath("blank-paper-log.png")
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Define the log graph area coordinates
    height, width, _ = img.shape
    graph_top = int(height * 0.37)
    graph_bottom = int(height * 0.47)
    graph_left = int(width * 0.12)
    graph_right = int(width * 0.9)
    hour_step = (graph_right - graph_left) / 24
    
    # Define duty status levels (approximate pixel positions)
    status_levels = {
        'off_duty': graph_top,
        'sleeper': graph_top + (graph_bottom - graph_top) * 0.35,
        'driving': graph_top + (graph_bottom - graph_top) * 0.65,
        'on_duty': graph_bottom
    }
    
    # Create a figure
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.imshow(img)
    
    # Draw ELD lines
    prev_x, prev_y = None, None
    for i, (hour, status) in enumerate(hours):
        x = graph_left + hour * hour_step
        y = status_levels[status]
        
        if prev_x is not None and prev_y is not None:
            ax.scatter([x, x], [prev_y, y], color='red', zorder=2)
            ax.scatter(prev_x, prev_y, color='red', s=40, zorder=2)
            ax.scatter(x, y, color='red', s=40, zorder=2)
            ax.plot([x, x], [prev_y, y], color='black', linewidth=2, zorder=1)
            ax.plot([prev_x, x], [prev_y, prev_y], color='black', linewidth=2, zorder=1)
        
        prev_x, prev_y = x, y
    
    # Ensure the last point extends to the end
    last_x = graph_right
    ax.plot([prev_x, last_x], [prev_y, prev_y], color='black', linewidth=2, zorder=1)
    ax.scatter(last_x, prev_y, color='red', s=40, zorder=2)
    
    # Display the overlayed image
    plt.axis('off')
    plt.show()

# Example usage
draw_eld_lines([
    (0, 'off_duty'), (6, 'driving'), (9, 'sleeper'), (12, 'on_duty'), (18, 'sleeper')
])