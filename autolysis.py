# /// script
# requires-python = ">=3.9"
# dependencies = [
#    "markdown",
#    "openai",
#    "pandas",
#    "scikit-learn",
#    "seaborn",
#    "tabulate",
#    "tenacity",
# ]
# ///


import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import openai
from tenacity import retry, stop_after_attempt, wait_fixed
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Get the AIProxy API Key from environment variables
def get_aiproxy_token():
    token = os.environ["AIPROXY_TOKEN"]
    if not token:
        raise EnvironmentError(f"Environment variable AIPROXY_TOKEN not found.")
    return token

# Set the AIProxy API Key and Base URL
openai.api_key = get_aiproxy_token()

# Change the OpenAI API base URL (for aiproxy)
openai.api_base = "https://aiproxy.sanand.workers.dev/openai/v1" 

def call_openai(prompt, model="gpt-4o-mini"):    #aiproxy supports gpt-4o-mini only
    """Calls OpenAI ChatCompletion API."""
    try:                                                             #was getting error in this step had to use openai 0.28 (mentioned in the inline dependencies)
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,                                         #was intially using 50-100 token which resulted in poor plots and readme files having less content...increased in to 1500 for an engaging narrative.
            temperature=0.5,
        )
        return response['choices'][0]['message']['content'].strip()
    except openai.OpenAIError as e:  # Use OpenAIError for exception handling
        raise RuntimeError(f"OpenAI API error: {e}") from e


def load_csv(file_path):
    """Load CSV file with automatic encoding detection."""
    try:
        return pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding="ISO-8859-1")

def summarize_dataset(df):
    """Generate a summary of the dataset."""
    summary = {
        "num_rows": df.shape[0],
        "num_columns": df.shape[1],
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "missing": df[col].isnull().sum(),
                "examples": df[col].dropna().sample(min(5, df[col].dropna().shape[0])).tolist() if not df[col].dropna().empty else []
            }
            for col in df.columns
        ],
    }
    return summary

def visualize_data(df):
    """Generate visualizations and save as PNG."""
    png_files = []

    # Correlation heatmap for numeric columns
    numeric_df = df.select_dtypes(include=['float64', 'int64'])
    if not numeric_df.empty:
        plt.figure(figsize=(10, 8))
        sns.heatmap(numeric_df.corr(), annot=True, fmt=".2f", cmap="coolwarm")
        heatmap_file = "dataset_correlation_heatmap.png"
        plt.title("Correlation Heatmap")
        plt.savefig(heatmap_file)
        plt.close()
        png_files.append(heatmap_file)

    # Categorical count plots for up to 3 categorical columns
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    for i, col in enumerate(categorical_cols[:3]):
        plt.figure(figsize=(10, 6))
        sns.countplot(data=df, y=col, order=df[col].value_counts().index[:10])
        plt.title(f"Count Plot for {col}")
        countplot_file = f"dataset_{col}_countplot.png"
        plt.savefig(countplot_file)
        plt.close()
        png_files.append(countplot_file)

    return png_files

def detect_clusters(df):
    """Perform clustering on numeric data."""
    numeric_df = df.select_dtypes(include=['float64', 'int64']).dropna()
    if numeric_df.shape[0] < 2 or numeric_df.shape[1] < 2:
        return "Insufficient data for clustering."

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(numeric_df)

    kmeans = KMeans(n_clusters=3, random_state=42)
    clusters = kmeans.fit_predict(scaled_data)
    numeric_df['Cluster'] = clusters
    return numeric_df

def generate_readme(summary, png_files):
    """
    Generate README.md with analysis results as a narrated story.

    Args:
        summary (str): Text summary of the dataset and analysis.
        png_files (list): List of PNG file names generated during the analysis.
    """
    prompt = (
        f"Imagine you're an expert storyteller narrating the tale of a dataset's journey. "
        f"The dataset contains the following summary:\n{summary}\n\n"
        f"Your task:\n"
        f"1. Write a rich, vivid story with an engaging introduction, narrating the dataset's discovery, "
        f"exploration, and the key insights it revealed.\n"
        f"2. Divide the story into sections:\n"
        f"   - Introduction: The dataset as a character and its context.\n"
        f"   - The Journey: The analysis process as a discovery adventure.\n"
        f"   - The Insights: The major findings as revelations.\n"
        f"   - Visual Clues: Each visualization as a key moment.\n"
        f"   - Conclusion: The impact and next steps.\n\n"
        f"3. Include descriptions for visualizations: {', '.join(png_files)}.\n"
        f"4. Write a minimum of 500 words in Markdown format.\n"
    )

    # Call the LLM and handle truncation issues (had to take help of chatgpt in this step to handle the error of some sentences in the readme file getting cutoff from mid sentences)
    story_part1 = call_openai(prompt + "Write the introduction and journey sections only.")
    story_part2 = call_openai(prompt + "Write the insights and visualizations sections only.")
    story_part3 = call_openai(prompt + "Write the conclusion and summarize the full narrative.")

    # Combine all parts into a cohesive README
    story = story_part1 + "\n\n" + story_part2 + "\n\n" + story_part3

    if not story.strip():
        print("Failed to generate a detailed README story.")
        return

    # Write to README.md with visualizations
    with open("README.md", "w") as readme:
        readme.write(story)
        readme.write("\n\n## Visualizations\n")
        for img in png_files:
            readme.write(f"![{img}]({img})\n\n")
            readme.write(f"**Figure: {img.split('.')[0].replace('_', ' ').title()}**\n")




    if not story:
        print("Failed to generate narrated README from LLM.")
        return

    with open("README.md", "w") as readme:
        readme.write(story)
        readme.write("\n\n## Visualizations\n")
        for img in png_files:
            readme.write(f"![{img}]({img})\n\n")
            readme.write(f"**Figure: {img.split('.')[0].replace('_', ' ').title()}**\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    csv_file = sys.argv[1]

    if not os.path.isfile(csv_file):
        print(f"Error: File {csv_file} not found.")
        sys.exit(1)

    try:
        # Load the dataset
        df = load_csv(csv_file)

        # Analyze and visualize the dataset
        dataset_summary = summarize_dataset(df)
        generated_images = visualize_data(df)

        # Perform clustering (if applicable)  additional file..
        clustering_result = detect_clusters(df)
        if isinstance(clustering_result, pd.DataFrame):
            clustering_result.to_csv("clustering_result.csv", index=False)
            print("Clustering result saved to 'clustering_result.csv'.")
        else:
            print("Clustering Result:", clustering_result)


        # Create README.md
        generate_readme(dataset_summary, generated_images)

        print("Analysis complete. Outputs saved:")
        print("- README.md")
        for img in generated_images:
            print(f"- {img}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

