import yfinance as yf
import pandas as pd
import numpy as np

def test_bollinger_bands():
    # Download test data
    data = yf.download("AAPL", period="1y", interval="1d", auto_adjust=True)
    print("Data downloaded successfully")
    
    # Calculate middle band
    data['BB_middle'] = data['Close'].rolling(window=20).mean()
    print("Middle band calculated")
    
    # Calculate standard deviation
    bb_std = data['Close'].rolling(window=20).std()
    if isinstance(bb_std, pd.DataFrame):
        bb_std = bb_std.iloc[:, 0]
    print("Standard deviation calculated")
    print(f"bb_std type: {type(bb_std)}")
    print(f"bb_std shape: {bb_std.shape}")
    
    # Calculate upper and lower bands
    data['BB_upper'] = data['BB_middle'] + (bb_std * 2)
    data['BB_lower'] = data['BB_middle'] - (bb_std * 2)
    print("Upper and lower bands calculated")
    
    # Print results
    print("\nBollinger Bands calculation test:")
    print("Last row values:")
    print(f"Close: {data['Close'].iloc[-1]}")
    print(f"BB Middle: {data['BB_middle'].iloc[-1]}")
    print(f"BB Upper: {data['BB_upper'].iloc[-1]}")
    print(f"BB Lower: {data['BB_lower'].iloc[-1]}")
    
    return data

if __name__ == "__main__":
    test_bollinger_bands() 