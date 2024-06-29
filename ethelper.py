import streamlit as st
import pandas as pd
import os
import time
import shutil
import matplotlib.pyplot as plt
import subprocess
import requests
import webbrowser

# Ensure the output directory exists
if not os.path.exists('output'):
    os.makedirs('output')

# Initialize session state for dataset generation status
if 'dataset_generated' not in st.session_state:
    st.session_state['dataset_generated'] = False

# Function to create a pie chart
def create_pie_chart(percentage, title):
    fig, ax = plt.subplots()
    ax.pie([percentage, 100 - percentage], colors=['#1f77b4', '#d3d3d3'], startangle=90, counterclock=False)
    ax.text(0, 0, f'{percentage}%', ha='center', va='center', fontsize=12, color='white')
    ax.set_title(title, fontsize=12, color='white')
    fig.patch.set_facecolor('black')
    return fig

# Function to load preset keys from a CSV file
def load_preset(preset_name):
    try:
        preset_df = pd.read_csv(f'presets/{preset_name}.csv', header=None)
        preset_keys = preset_df.iloc[0].tolist()
        return preset_keys
    except FileNotFoundError:
        st.error(f"Preset file '{preset_name}.csv' not found in the 'presets' directory.")
        return []

# Function to load categories for a preset
def load_categories(preset_name):
    try:
        categories_df = pd.read_csv(f'presets/categories/{preset_name}/categories.csv', header=None)
        categories = {
            'keys': categories_df.iloc[0].tolist(),
            'level': [level.capitalize() for level in categories_df.iloc[1].tolist()],
            'typology': [typology.capitalize() for typology in categories_df.iloc[2].tolist()]
        }    
        return categories
    except FileNotFoundError:
        st.error(f"Category file for '{preset_name}' not found in the 'presets/categories' directory.")
        return {}

# Function to load default values for a preset
def load_defaults(default_file):
    try:
        defaults_df = pd.read_csv(f'presets/defaults/{default_file}.csv', header=None)
        defaults = dict(zip(defaults_df.iloc[0], defaults_df.iloc[1]))
        return defaults
    except FileNotFoundError:
        st.error(f"Default file '{default_file}.csv' not found in the 'presets/defaults' directory.")
        return {}

# Function to load the default file name for a preset from the defaultlist.csv
def get_default_file(preset_name):
    try:
        defaultlist_df = pd.read_csv('config/defaultlist.csv', header=None)
        default_dict = dict(zip(defaultlist_df.iloc[0], defaultlist_df.iloc[1]))
        return default_dict.get(preset_name, None)
    except FileNotFoundError:
        st.error("defaultlist.csv not found in the 'presets' directory.")
        return None

# Function to get the most recent migration folder
def get_most_recent_migration():
    migrate_path = os.path.join('..', 'etlocal', 'db', 'migrate')
    list_of_folders = [f for f in os.listdir(migrate_path) if os.path.isdir(os.path.join(migrate_path, f))]
    if list_of_folders:
        most_recent_folder = max(list_of_folders, key=lambda f: os.path.getctime(os.path.join(migrate_path, f)))
        return most_recent_folder
    else:
        return None

# Function to update the CSVImporter.run command in the required .rb file
def update_rb_file(migration_name):
    base_path = os.path.abspath(os.path.join(os.getcwd(), '..'))
    rb_file_path = os.path.join(base_path, 'etlocal', 'db', 'migrate', f'{migration_name}.rb')

    with open(rb_file_path, 'r') as file:
        lines = file.readlines()

    with open(rb_file_path, 'w') as file:
        for line in lines:
            if 'CSVImporter.run' in line:
                line = line.replace('CSVImporter.run(data_path, commits_path)', 'CSVImporter.run(data_path, commits_path, create_missing_datasets: true)')
            file.write(line)

# Load the keys CSV file
def load_keys():
    try:
        df_keys = pd.read_csv('variables/keys.csv', header=None)  # Read without header
        return df_keys
    except FileNotFoundError:
        st.error("variables/keys.csv not found. Please ensure the file is in the correct directory.")
        return pd.DataFrame()

# Function to load the translations CSV file
def load_translations():
    try:
        df_translations = pd.read_csv('variables/translations.csv', header=None)  # Read without header
        return df_translations
    except FileNotFoundError:
        st.error("variables/translations.csv not found. Please ensure the file is in the correct directory.")
        return pd.DataFrame()

# Function to initialize session state for keys
def initialize_keys(df_keys):
    # Ensure the keys CSV file is not empty and has content
    if df_keys.empty or df_keys.shape[1] == 0:
        st.error("variables/keys.csv is empty or improperly formatted. Please ensure the file has the correct format.")
        return [], []

    # Extract keys from the first row of keys.csv
    keys = df_keys.iloc[0].tolist()

    # Extract translations from the second row of translations.csv
    df_translations = load_translations()
    if df_translations.empty or df_translations.shape[1] == 0:
        st.error("variables/translations.csv is empty or improperly formatted. Please ensure the file has the correct format.")
        return [], []

    translations = df_translations.iloc[1].tolist()

    # Initialize all keys in the session state
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = ""

    return keys, translations

# Function to find a specific directory relative to the script's location
def find_directory(dir_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    dir_path = os.path.join(parent_dir, dir_name)

    if not os.path.exists(dir_path):
        st.error(f"{dir_name} directory not found. Make sure it exists in the same location as the folder containing this script.")
        return None

    return dir_path

# Function to extract admin password from setup output
def extract_admin_password(output):
    password_line = "Created admin user admin@example.org with password:"
    start_index = output.find(password_line) + len(password_line)
    end_index = output.find("\n", start_index)
    admin_password = output[start_index:end_index].strip().rstrip('|').strip()
    return admin_password

# Function to extract client_id and client_secret from the configuration output
def extract_identity_info(config_content):
    lines = config_content.split('\n')
    client_id = ""
    client_secret = ""
    for line in lines:
        if "client_id:" in line:
            client_id = line.split(":")[1].strip()
        if "client_secret:" in line:
            client_secret = line.split(":")[1].strip()
    return client_id, client_secret

# Function to update settings.local.yml in etmodel directory
def update_settings_file(client_id, client_secret):
    etmodel_path = find_directory("etmodel")

    if etmodel_path:
        config_path = os.path.join(etmodel_path, "config", "settings.local.yml")
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                config_lines = file.readlines()

            with open(config_path, 'w') as file:
                for line in config_lines:
                    if "client_id:" in line:
                        file.write(f"  client_id: {client_id}\n")
                    elif "client_secret:" in line:
                        file.write(f"  client_secret: {client_secret}\n")
                    else:
                        file.write(line)
            st.success(f"Updated settings.local.yml with new client_id and client_secret.")
        else:
            st.error(f"settings.local.yml not found in {etmodel_path}/config.")

# Function to execute Docker commands sequentially
def execute_docker_commands(dir_name, setup_complete_message):
    repo_path = find_directory(dir_name)

    if repo_path:
        # Change directory to the specified repository
        os.chdir(repo_path)

        commands = [
            "docker-compose build",                                    # Build Docker containers
            "docker-compose run --rm web bundle install",              # Bundle install
            "docker-compose run --rm web bash -c 'bin/rails db:drop && bin/setup'",  # Database setup
            "docker-compose up -d"                                     # Start containers in detached mode
        ]

        outputs = []
        admin_password = None

        for cmd in commands:
            st.write(f"Executing command: {cmd}")
            st.info("Running command...")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Display command output
            outputs.append(result.stdout)
            if dir_name == "etengine":
                st.session_state.etengine_outputs.append(result.stdout)
                if "Created admin user admin@example.org with password:" in result.stdout:
                    admin_password = extract_admin_password(result.stdout)
                    st.session_state.etengine_admin_password = admin_password
            else:
                st.session_state.etmodel_outputs.append(result.stdout)
            
            if result.returncode != 0:
                st.error(f"Command '{cmd}' failed with error code {result.returncode}")
                st.text(result.stderr)
                return False, outputs
            
        st.success(setup_complete_message)
        return True, outputs

    return False, []

def wait_for_server(url, timeout=60):
    """Wait for the server at the specified URL to become responsive."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(5)
    return False

# Streamlit app
def main():

    # Home Menu (no need for keys.csv)
    if menu == "Home":
        st.image('icons/logos.png', width=1000)
        col1, col2 = st.columns([1, 10])  # Adjust the ratio as needed

        with col1:
            pass  # Removing the dsgen.png image

        with col2:
            st.markdown(
                """
                <style>
                @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@700&display=swap');
                .title {
                    font-family: 'Roboto', sans-serif;
                    font-size: 102px;
                    text-align: left;
                    background: -webkit-linear-gradient(#eee, #333);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                </style>
                <h1 class="title">ETHelper</h1>
                """, 
                unsafe_allow_html=True
            )
        st.title('Dataset Generator for the ETM')
        st.write("Welcome to the dataset generator for the Energy Transition Model. This tool is used to create the files essential for dataset migrations within ETLocal, the ETM repository responsible for exporting datasets to ETSource.")
        st.write("There are 3 key menus that can be accessed through the toolbar on the left: Dataset Generation, Dataset Migration, and Dataset Visualisation")
        st.write("Dataset Generation allows users to input values for each key variable (key) that the ETM relies on to function. Users can generate the dataset into a data.csv file, which by default is created in the 'output' folder. Users can also download this file into their 'downloads' folder if desired.")
        st.write("Dataset Migration allows users to export the data.csv to the relevant migration in ETLocal, specifying the migration name in full.")
        st.write("Dataset Visualisation shows the current state of data.csv in a tabular and searchable format.")
        # Display dataset generation status
        if st.session_state['dataset_generated']:
            st.write("**Current Dataset Status:** DATASET GENERATED (✓)")
        else:
            st.write("**Current Dataset Status:** DATASET IN BUILD (☓)")
        st.image('icons/mappacific.png', width=500)
        st.write("For any questions or technical support, please email:")
        st.write("Edoardo Santagata")
        st.write("edoardo.santagata@unsw.edu.au")
        st.write("The University of New South Wales (UNSW)")

    # Dataset Generation Menu (requires keys.csv)
    elif menu == "Dataset Generation":
        df_keys = load_keys()
        if df_keys.empty:
            st.stop()

        keys, translations = initialize_keys(df_keys)
        if not keys or not translations:
            st.stop()

        st.title('Dataset Generation')
        st.write('Use the menu on the side to select a preset group of keys (which are modelled after specific countries). Displayed keys can be adjusted by level (basic or advanced) and typology (general, supply, demand, etc.). The "populate" buttons affect all keys, even the ones that are not visible or not part of the preset group.') 

        # Create a preset selection menu in the sidebar
        preset_files = [f.replace('.csv', '') for f in os.listdir('presets') if f.endswith('.csv')]
        selected_preset = st.sidebar.selectbox('Select a preset group of keys:', preset_files)

        # Load the selected preset keys and categories
        preset_keys = load_preset(selected_preset)
        categories = load_categories(selected_preset)

        # Ensure keys not in the selected preset are set to "0"
        for key in keys:
            if key not in preset_keys and st.session_state[key] == "":
                st.session_state[key] = "0"

        # Display the flag and title for the selected preset group
        col1, col2 = st.columns([1, 9])
        with col1:
            st.image(f'icons/flags/{selected_preset}.png', width=50)
        with col2:
            st.title('Data Entry Form')

        # Create placeholders for the progress pie charts and progress bar
        pie_placeholder_col1, pie_placeholder_col2 = st.columns(2)
        progress_placeholder_text = st.empty()
        progress_placeholder_bar = st.empty()

        # Button to populate empty inputs with "0" in the sidebar
        populate_button = st.sidebar.button('Populate Empty Values with 0')

        # Button to populate empty inputs with default basic values in the sidebar
        populate_basic_defaults_button = st.sidebar.button('Populate Empty Basic Keys with Default')

        # Button to populate empty inputs with default advanced values in the sidebar
        populate_advanced_defaults_button = st.sidebar.button('Populate Empty Advanced Keys with Default')

        # Button to generate dataset in the sidebar
        generate_button = st.sidebar.button('Generate Dataset')

        # Load default file for the selected preset
        default_file = get_default_file(selected_preset)
        if default_file:
            defaults = load_defaults(default_file)
        else:
            defaults = {}

        # Update session state with default values for basic keys if the button is clicked
        if populate_basic_defaults_button:
            for key in preset_keys:
                if categories and key in categories['keys']:
                    idx = categories['keys'].index(key)
                    level = categories['level'][idx]
                    if level == 'Basic' and st.session_state[key] == "":
                        st.session_state[key] = str(defaults.get(key, ""))

        # Update session state with default values for advanced keys if the button is clicked
        if populate_advanced_defaults_button:
            for key in preset_keys:
                if categories and key in categories['keys']:
                    idx = categories['keys'].index(key)
                    level = categories['level'][idx]
                    if level == 'Advanced' and st.session_state[key] == "":
                        st.session_state[key] = str(defaults.get(key, ""))

        # Update session state before widgets are created
        if populate_button:
            for key in preset_keys:
                if key not in st.session_state or st.session_state[key] == "":
                    st.session_state[key] = "0"
            # Increasing the delay to ensure the session state is fully updated
            time.sleep(0.5)

        user_input = {}
        total_preset_keys = len(preset_keys)
        completed_keys = 0
        completed_basic_keys = 0
        completed_advanced_keys = 0
        basic_keys = 0
        advanced_keys = 0
        keys_not_visible = []
        preset_keys_not_visible = []

        key_index = 1
        visible_key_index = 1

        for typology in ['General', 'Supply', 'Demand', 'Emissions', 'Conversion', 'Network', 'Heat']:
            with st.expander(typology):
                for key, translation in zip(keys, translations):
                    if key in preset_keys:
                        if categories and key in categories['keys']:
                            idx = categories['keys'].index(key)
                            level = categories['level'][idx]
                            key_typology = categories['typology'][idx]

                            value_inserted = st.session_state[key] != ""

                            if level == 'Basic' and key_typology == typology:
                                value = st.session_state[key]
                                user_input[key] = st.text_input(f"Enter value for {translation} ({key})", value=value, key=key)
                                if value != "":
                                    completed_keys += 1
                                    completed_basic_keys += 1
                                if debug_mode:
                                    st.write(f"#: {key_index}, Visible#: {visible_key_index}, Key: {key}, Level: {level}, Typology: {key_typology}, Show: True, Value: {value_inserted}, Session State: {st.session_state[key]}")
                                visible_key_index += 1
                                basic_keys += 1
                            else:
                                user_input[key] = st.session_state[key]
                                preset_keys_not_visible.append(key)
                                if debug_mode:
                                    st.write(f"#: {key_index}, Visible#: N/A, Key: {key}, Level: {level}, Typology: {key_typology}, Show: False, Value: {value_inserted}, Session State: {st.session_state[key]}")
                        else:
                            value = st.session_state[key]
                            user_input[key] = st.text_input(f"Enter value for {translation} ({key})", value=value, key=key)
                            if value != "":
                                completed_keys += 1
                            if debug_mode:
                                st.write(f"#: {key_index}, Visible#: {visible_key_index}, Key: {key}, Level: N/A, Typology: N/A, Show: True, Value: {value_inserted}, Session State: {st.session_state[key]}")
                            visible_key_index += 1
                    else:
                        user_input[key] = st.session_state.get(key, "0")
                        keys_not_visible.append(key)

                    key_index += 1

        with st.expander("Advanced"):
            for typology in ['General', 'Supply', 'Demand', 'Emissions', 'Conversion', 'Network', 'Heat']:
                st.subheader(typology)
                for key, translation in zip(keys, translations):
                    if key in preset_keys:
                        if categories and key in categories['keys']:
                            idx = categories['keys'].index(key)
                            level = categories['level'][idx]
                            key_typology = categories['typology'][idx]

                            value_inserted = st.session_state[key] != ""

                            if level == 'Advanced' and key_typology == typology:
                                value = st.session_state[key]
                                user_input[key] = st.text_input(f"Enter value for {translation} ({key})", value=value, key=key)
                                if value != "":
                                    completed_keys += 1
                                    completed_advanced_keys += 1
                                if debug_mode:
                                    st.write(f"#: {key_index}, Visible#: {visible_key_index}, Key: {key}, Level: {level}, Typology: {key_typology}, Show: True, Value: {value_inserted}, Session State: {st.session_state[key]}")
                                visible_key_index += 1
                                advanced_keys += 1
                            else:
                                user_input[key] = st.session_state[key]
                                preset_keys_not_visible.append(key)
                                if debug_mode:
                                    st.write(f"#: {key_index}, Visible#: N/A, Key: {key}, Level: {level}, Typology: {key_typology}, Show: False, Value: {value_inserted}, Session State: {st.session_state[key]}")
                        else:
                            value = st.session_state[key]
                            user_input[key] = st.text_input(f"Enter value for {translation} ({key})", value=value, key=key)
                            if value != "":
                                completed_keys += 1
                            if debug_mode:
                                st.write(f"#: {key_index}, Visible#: {visible_key_index}, Key: {key}, Level: N/A, Typology: N/A, Show: True, Value: {value_inserted}, Session State: {st.session_state[key]}")
                            visible_key_index += 1
                    else:
                        user_input[key] = st.session_state.get(key, "0")
                        keys_not_visible.append(key)

                    key_index += 1

        progress_percentage = int((completed_keys / total_preset_keys) * 100)
        basic_completion_percentage = int((completed_basic_keys / basic_keys) * 100) if basic_keys > 0 else 0
        advanced_completion_percentage = int((completed_advanced_keys / advanced_keys) * 100) if advanced_keys > 0 else 0

        # Display the progress pie charts just below the title
        with pie_placeholder_col1:
            st.pyplot(create_pie_chart(basic_completion_percentage, 'Basic Keys Completion'))
        with pie_placeholder_col2:
            st.pyplot(create_pie_chart(advanced_completion_percentage, 'Advanced Keys Completion'))

        # Show progress bar and numerical percentage below the 'Data Entry Form' title
        progress_placeholder_text.write(f"Completion: {progress_percentage}% ({completed_keys}/{total_preset_keys})")
        progress_placeholder_bar.progress(progress_percentage)

        if debug_mode:
            if keys_not_visible:
                st.write("Keys from keys.csv not currently visible:")
                for i, key in enumerate(keys_not_visible, start=1):
                    st.write(f"#: {i}, Key: {key}")
            if preset_keys_not_visible:
                st.write("Keys from the selected preset group not currently visible:")
                for i, key in enumerate(preset_keys_not_visible, start=1):
                    st.write(f"#: {i}, Key: {key}")

            # Debugging statements for advanced keys
            st.write(f"Total Advanced Keys: {advanced_keys}")
            st.write(f"Completed Advanced Keys: {completed_advanced_keys}")

        if generate_button:
            new_df = pd.DataFrame([user_input])
            output_file_path = 'output/data.csv'
            new_df.to_csv(output_file_path, index=False)
            st.success("data.csv generated successfully")
            st.download_button(
                label="Download CSV",
                data=new_df.to_csv(index=False),
                file_name='data.csv',
                mime='text/csv'
            )
            st.session_state['dataset_generated'] = True

    # Dataset Visualisation Menu (requires keys.csv)
    elif menu == "Dataset Visualisation":
        st.title('Dataset Visualisation')
        st.write('This section allows you to inspect the dataset that was generated. This dataset is saved in data.csv and is ready to be exported. It is always a good idea to check that empty keys have been automatically populated with the desired inputs by searching "nan" in the dataset viewer')

        try:
            data_df = pd.read_csv('output/data.csv')
            st.write("Current content of data.csv:")
            st.dataframe(data_df.astype(str).transpose())
        except FileNotFoundError:
            st.error("output/data.csv not found. Please generate the dataset first.")
        except pd.errors.EmptyDataError:
            st.error("output/data.csv is empty.")

    # Dataset Migration Menu (requires keys.csv)
    elif menu == "Dataset Migration":
        st.title('Dataset Migration')
        st.write('Please generate a new migration in ETLocal and input the generated folder name in etlocal/db/migrate as the migration name. This ensures the data.csv file will be copied to the correct migration')

        # Display the most recent migration folder
        if st.button('Fetch Most Recent Migration'):
            most_recent_migration = get_most_recent_migration()
            if most_recent_migration:
                st.write(f"Most recent migration: {most_recent_migration}")
            else:
                st.write("No migration folders found.")

        # Text input for the migration name
        migration_name = st.text_input("Enter the migration name:")

        if st.button('Update Migration'):
            if migration_name:
                base_path = os.path.abspath(os.path.join(os.getcwd(), '..'))
                destination_dir = os.path.join(base_path, 'etlocal', 'db', 'migrate', migration_name)
                if not os.path.exists(destination_dir):
                    os.makedirs(destination_dir)
                try:
                    shutil.copy('output/data.csv', destination_dir)
                    shutil.copy('output/commits.yml', os.path.join(destination_dir, 'commits.yml'))
                    update_rb_file(migration_name)
                    st.success(f"data.csv, commits.yml, and {migration_name}.rb updated successfully")
                except Exception as e:
                    st.error(f"Failed to update migration: {e}")
            else:
                st.error("Please enter a valid migration name.")

    # ETM Local Run Menu (no need for keys.csv)
    elif menu == "ETM Local Run":
        st.title('ETM Local Run')
        st.write('This section automates the setup for the ETEngine (calculation engine) and ETModel (model interface) repositories. Please set them up one at the time and make sure to open ETEngine before setting up ETModel to avoid errors (TBF).')

        if 'etengine_setup_complete' not in st.session_state:
            st.session_state.etengine_setup_complete = False
        if 'etmodel_setup_complete' not in st.session_state:
            st.session_state.etmodel_setup_complete = False
        if 'etengine_outputs' not in st.session_state:
            st.session_state.etengine_outputs = []
        if 'etmodel_outputs' not in st.session_state:
            st.session_state.etmodel_outputs = []
        if 'etengine_admin_password' not in st.session_state:
            st.session_state.etengine_admin_password = None

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Setup ETEngine") and not st.session_state.etengine_setup_complete:
                setup_successful, _ = execute_docker_commands("etengine", "ETEngine setup complete, available on localhost:3000")
                if setup_successful:
                    st.session_state.etengine_setup_complete = True
                    st.write("ETEngine setup complete, available on localhost:3000")
                    
            if st.session_state.etengine_setup_complete:
                if st.button("Open Engine"):
                    webbrowser.open_new_tab("http://localhost:3000")

        with col2:
            if st.button("Setup ETModel") and not st.session_state.etmodel_setup_complete:
                setup_successful, _ = execute_docker_commands("etmodel", "ETModel setup complete, available on localhost:3001")
                if setup_successful:
                    st.session_state.etmodel_setup_complete = True
                    st.write("ETModel setup complete, available on localhost:3001")
                    wait_for_server("http://localhost:3001")
                    
            if st.session_state.etmodel_setup_complete:
                if st.button("Open ETM"):
                    webbrowser.open_new_tab("http://localhost:3001")

        if st.session_state.etengine_setup_complete and st.session_state.etengine_admin_password:
            st.markdown(f"**ETEngine Login Details:**\n- **User:** admin@example.org\n- **PW:** {st.session_state.etengine_admin_password}")

        with st.expander("ETEngine Deployment Outputs"):
            for output in st.session_state.etengine_outputs:
                st.code(output)

        with st.expander("ETModel Deployment Outputs"):
            for output in st.session_state.etmodel_outputs:
                st.code(output)

if __name__ == "__main__":
    # Create a sidebar menu
    menu = st.sidebar.selectbox(
        "Select a Menu",
        ("Home", "Dataset Generation", "Dataset Visualisation", "Dataset Migration","ETM Local Run")
    )

    # Add checkbox for enabling or disabling debugging
    debug_mode = st.sidebar.checkbox('Enable Debugging')

    main()
